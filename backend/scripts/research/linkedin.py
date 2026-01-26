"""LinkedIn company profile extractor."""

import re
import sys
import time
from pathlib import Path

from playwright.sync_api import Page, sync_playwright

from scripts.research.base import BaseExtractor
from scripts.research.remote import get_extractor_js

# Use LinkedIn's persistent profile (same as job scraper)
LINKEDIN_PROFILE_DIR = Path(__file__).parent.parent.parent.parent / "data" / "linkedin_profile"


class LinkedInExtractor(BaseExtractor):
    """Extract company data from LinkedIn company pages."""

    name = "linkedin"

    def extract(self, url: str) -> dict:
        """Extract data from LinkedIn, using existing auth session."""
        LINKEDIN_PROFILE_DIR.mkdir(parents=True, exist_ok=True)
        self._clear_linkedin_lock()

        with sync_playwright() as p:
            context = p.chromium.launch_persistent_context(
                str(LINKEDIN_PROFILE_DIR),
                headless=True,
                channel="chromium",
            )
            page = context.new_page()

            try:
                page.goto(url, wait_until="domcontentloaded", timeout=30000)
                time.sleep(2)

                # Check if logged in
                if not self._is_logged_in(page):
                    context.close()
                    print("Not logged in to LinkedIn. Run 'jbs login' first.", file=sys.stderr)
                    return {"error": "Not logged in. Run 'jbs login' first."}

                return self._run_extraction(page)
            finally:
                context.close()

    def _clear_linkedin_lock(self):
        """Clear LinkedIn profile lock file."""
        lock_file = LINKEDIN_PROFILE_DIR / "SingletonLock"
        if lock_file.exists() or lock_file.is_symlink():
            try:
                lock_file.unlink()
            except OSError:
                pass

    def _is_logged_in(self, page: Page) -> bool:
        """Check if user is logged into LinkedIn."""
        return page.query_selector('input[aria-label*="Search"]') is not None

    def _run_extraction(self, page: Page) -> dict:
        """Extract company data from LinkedIn company page."""
        result = {
            "source": "linkedin",
            "url": page.url,
        }

        # Ensure we're on the "about" tab for full info
        if "/about" not in page.url:
            about_url = page.url.rstrip("/") + "/about/"
            about_url = re.sub(r'/+about/+', '/about/', about_url)
            try:
                page.goto(about_url, wait_until="domcontentloaded", timeout=15000)
                time.sleep(2)
            except Exception:
                pass  # Continue with current page

        # Fetch and run remote JS extraction
        try:
            js_code = get_extractor_js("linkedin")
            extracted = page.evaluate(js_code)
            if extracted:
                result.update(extracted)
        except Exception:
            pass

        # Fallback: try regex on page content if JS extraction failed
        if len(result) <= 2:  # Only source and url
            content = page.content()
            self._extract_from_html(content, result)

        return result

    def _extract_from_html(self, content: str, result: dict):
        """Fallback extraction from raw HTML."""
        # Employee count
        patterns = [
            r'(\d{1,3}(?:,\d{3})*(?:-\d{1,3}(?:,\d{3})*)?)\s+employees\s+on\s+LinkedIn',
            r'Company size[:\s]*(\d{1,3}(?:,\d{3})*(?:-\d{1,3}(?:,\d{3})*)?)',
        ]
        for pattern in patterns:
            match = re.search(pattern, content, re.I)
            if match:
                result["employees"] = match.group(1)
                break

        # Headquarters
        hq_match = re.search(r'Headquarters?[:\s]*([^<\n]{5,50})', content, re.I)
        if hq_match:
            result["hq"] = re.sub(r'<[^>]+>', '', hq_match.group(1)).strip()

        # Industry
        ind_match = re.search(r'Industry[:\s]*([^<\n]{5,50})', content, re.I)
        if ind_match:
            result["industry"] = re.sub(r'<[^>]+>', '', ind_match.group(1)).strip()

        # Founded
        founded_match = re.search(r'Founded[:\s]*(\d{4})', content, re.I)
        if founded_match:
            result["founded"] = founded_match.group(1)
