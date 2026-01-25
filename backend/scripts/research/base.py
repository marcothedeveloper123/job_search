"""Base extractor with Cloudflare handling for web research."""

import sys
import time
from abc import ABC, abstractmethod
from pathlib import Path

from playwright.sync_api import Page, sync_playwright

# Shared browser profile directory
PROFILE_DIR = Path(__file__).parent.parent.parent.parent / "data" / "research_profile"


class BaseExtractor(ABC):
    """Base class for web research extractors with Cloudflare handling."""

    name: str = "base"

    def extract(self, url: str) -> dict:
        """Extract data from URL, handling Cloudflare if needed."""
        PROFILE_DIR.mkdir(parents=True, exist_ok=True)
        self._clear_lock_file()

        with sync_playwright() as p:
            # Try headless first
            page = self._launch(p, url, headless=True)

            if self._is_cloudflare(page):
                page.context.close()
                # Reopen visible for manual solving
                print("Cloudflare detected. Solve the CAPTCHA in the browser...", file=sys.stderr)
                page = self._launch(p, url, headless=False)
                self._wait_for_cloudflare(page)
                print("CAPTCHA solved. Extracting...", file=sys.stderr)

            try:
                return self._run_extraction(page)
            finally:
                page.context.close()

    @abstractmethod
    def _run_extraction(self, page: Page) -> dict:
        """Extract structured data from page. Implement in subclass."""
        pass

    def _launch(self, playwright, url: str, headless: bool) -> Page:
        """Launch browser and navigate to URL."""
        context = playwright.chromium.launch_persistent_context(
            str(PROFILE_DIR),
            headless=headless,
            channel="chromium",
        )
        page = context.new_page()
        page.goto(url, wait_until="domcontentloaded", timeout=30000)
        time.sleep(2)  # Let page settle
        return page

    def _is_cloudflare(self, page: Page) -> bool:
        """Check if page shows Cloudflare challenge."""
        try:
            title = page.title().lower()
            if "just a moment" in title or "cloudflare" in title:
                return True
            # Check for challenge elements
            content = page.content().lower()
            return "cf-challenge" in content or "checking your browser" in content
        except Exception:
            # Page navigated or context destroyed - likely CAPTCHA was solved
            return False

    def _wait_for_cloudflare(self, page: Page, timeout: int = 120):
        """Wait for user to solve Cloudflare challenge."""
        for _ in range(timeout):
            try:
                if not self._is_cloudflare(page):
                    time.sleep(1)  # Extra settle time
                    return
            except Exception:
                # Page navigated - CAPTCHA likely solved
                time.sleep(1)
                return
            time.sleep(1)
        print("Cloudflare timeout. Attempting extraction anyway...", file=sys.stderr)

    def _clear_lock_file(self):
        """Clear stale browser lock file."""
        lock_file = PROFILE_DIR / "SingletonLock"
        if lock_file.exists() or lock_file.is_symlink():
            try:
                lock_file.unlink()
            except OSError:
                pass

    def _safe_text(self, page: Page, selector: str) -> str | None:
        """Safely extract text from selector, return None if not found."""
        try:
            el = page.query_selector(selector)
            return el.inner_text().strip() if el else None
        except Exception:
            return None

    def _safe_attr(self, page: Page, selector: str, attr: str) -> str | None:
        """Safely extract attribute from selector."""
        try:
            el = page.query_selector(selector)
            return el.get_attribute(attr) if el else None
        except Exception:
            return None

    def _safe_all_text(self, page: Page, selector: str, limit: int = 10) -> list[str]:
        """Extract text from all matching elements."""
        try:
            els = page.query_selector_all(selector)[:limit]
            return [el.inner_text().strip() for el in els if el.inner_text().strip()]
        except Exception:
            return []
