"""LinkedIn authentication management."""

import time
from pathlib import Path

from playwright.sync_api import sync_playwright

# Profile directory at project root (shared with scrapers)
PROFILE_DIR = Path(__file__).parent.parent.parent / "data" / "linkedin_profile"


def _clear_lock():
    """Clear stale Chromium lock file."""
    lock_file = PROFILE_DIR / "SingletonLock"
    if lock_file.exists():
        lock_file.unlink()


def check_auth_status() -> dict:
    """
    Check if LinkedIn session is valid.

    Returns:
        {"status": "ok", "authenticated": True/False}
    """
    if not PROFILE_DIR.exists():
        return {"status": "ok", "authenticated": False}

    _clear_lock()

    try:
        with sync_playwright() as p:
            context = p.chromium.launch_persistent_context(
                str(PROFILE_DIR),
                headless=True,
                channel="chromium",
            )
            page = context.new_page()

            try:
                page.goto("https://www.linkedin.com/feed/", wait_until="domcontentloaded", timeout=15000)
                time.sleep(2)

                url = page.url

                # Redirected to login = not authenticated
                if "login" in url or "signup" in url:
                    return {"status": "ok", "authenticated": False}

                # On feed page - check for nav element
                nav = page.query_selector('nav')
                if nav:
                    return {"status": "ok", "authenticated": True}

                # On feed but nav not found = selector broken, not auth failure
                return {
                    "status": "error",
                    "error": f"Auth check failed: on {url} but nav element not found",
                    "code": "SELECTOR_BROKEN",
                }

            finally:
                context.close()

    except Exception as e:
        return {"status": "error", "error": str(e), "code": "AUTH_FAILED"}


def do_login() -> dict:
    """
    Open browser for manual LinkedIn login.

    Blocks until login completes or times out (2 minutes).

    Returns:
        {"status": "ok", "authenticated": True} on success
        {"status": "error", "error": "...", "code": "AUTH_FAILED"} on failure
    """
    PROFILE_DIR.mkdir(parents=True, exist_ok=True)
    _clear_lock()

    try:
        with sync_playwright() as p:
            context = p.chromium.launch_persistent_context(
                str(PROFILE_DIR),
                headless=False,
                channel="chromium",
            )
            page = context.new_page()

            try:
                page.goto("https://www.linkedin.com/login")

                # Wait for navigation away from login/checkpoint pages
                for _ in range(120):  # 2 minute timeout
                    time.sleep(1)
                    url = page.url
                    if "/feed" in url or "/jobs" in url or "/mynetwork" in url:
                        return {"status": "ok", "authenticated": True}

                return {"status": "error", "error": "Login timeout", "code": "AUTH_FAILED"}

            finally:
                context.close()

    except Exception as e:
        return {"status": "error", "error": str(e), "code": "AUTH_FAILED"}
