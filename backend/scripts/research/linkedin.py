"""LinkedIn company profile extractor."""

import re
import sys
import time
from pathlib import Path

from playwright.sync_api import Page, sync_playwright

from scripts.research.base import BaseExtractor

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
                time.sleep(1)
            except Exception:
                pass  # Continue with current page

        # Company name
        name = self._extract_name(page)
        if name:
            result["name"] = name

        # Employee count
        employees = self._extract_employees(page)
        if employees:
            result["employees"] = employees

        # Headquarters
        hq = self._extract_hq(page)
        if hq:
            result["hq"] = hq

        # Industry
        industry = self._extract_industry(page)
        if industry:
            result["industry"] = industry

        # Founded year
        founded = self._extract_founded(page)
        if founded:
            result["founded"] = founded

        # Website
        website = self._extract_website(page)
        if website:
            result["website"] = website

        # Specialties
        specialties = self._extract_specialties(page)
        if specialties:
            result["specialties"] = specialties

        # Company type
        company_type = self._extract_type(page)
        if company_type:
            result["type"] = company_type

        # Description
        desc = self._extract_description(page)
        if desc:
            result["description"] = desc

        return result

    def _extract_name(self, page: Page) -> str | None:
        """Extract company name."""
        selectors = [
            'h1[class*="org-top-card"]',
            'h1.ember-view',
            'h1',
        ]
        for sel in selectors:
            text = self._safe_text(page, sel)
            if text and len(text) < 100:
                return text.strip()
        return None

    def _extract_employees(self, page: Page) -> str | None:
        """Extract employee count."""
        content = page.content()

        # LinkedIn shows "X employees" or "X,XXX employees"
        patterns = [
            r'([\d,]+(?:-[\d,]+)?)\s*employees?\s*on\s*LinkedIn',
            r'([\d,]+(?:-[\d,]+)?)\s*employees?',
            r'Company size[:\s]*([\d,]+(?:-[\d,]+)?)',
        ]
        for pattern in patterns:
            match = re.search(pattern, content, re.I)
            if match:
                return match.group(1)

        # Try specific selectors
        selectors = [
            '[class*="employee-count"]',
            'dd:has(+ dt:text("Company size"))',
        ]
        for sel in selectors:
            text = self._safe_text(page, sel)
            if text:
                match = re.search(r'([\d,]+)', text)
                if match:
                    return match.group(1)

        return None

    def _extract_hq(self, page: Page) -> str | None:
        """Extract headquarters location."""
        content = page.content()

        patterns = [
            r'Headquarters?[:\s]*([^<\n]+)',
            r'HQ[:\s]*([^<\n]+)',
        ]
        for pattern in patterns:
            match = re.search(pattern, content, re.I)
            if match:
                hq = match.group(1).strip()
                # Clean up
                hq = re.sub(r'<[^>]+>', '', hq)
                if len(hq) < 100:
                    return hq

        return None

    def _extract_industry(self, page: Page) -> str | None:
        """Extract industry."""
        content = page.content()

        patterns = [
            r'Industry[:\s]*([^<\n]+)',
        ]
        for pattern in patterns:
            match = re.search(pattern, content, re.I)
            if match:
                industry = match.group(1).strip()
                industry = re.sub(r'<[^>]+>', '', industry)
                if len(industry) < 100:
                    return industry

        return None

    def _extract_founded(self, page: Page) -> str | None:
        """Extract founded year."""
        content = page.content()

        patterns = [
            r'Founded[:\s]*(\d{4})',
        ]
        for pattern in patterns:
            match = re.search(pattern, content, re.I)
            if match:
                return match.group(1)

        return None

    def _extract_website(self, page: Page) -> str | None:
        """Extract company website."""
        content = page.content()

        # Look for website link
        patterns = [
            r'Website[:\s]*<[^>]*href="([^"]+)"',
            r'href="(https?://(?:www\.)?[^"]+)"[^>]*>.*?[Vv]isit',
        ]
        for pattern in patterns:
            match = re.search(pattern, content)
            if match:
                url = match.group(1)
                if "linkedin.com" not in url:
                    return url

        # Try selector
        selectors = [
            'a[href*="http"]:has-text("Visit")',
            '[data-test-id*="website"] a',
        ]
        for sel in selectors:
            href = self._safe_attr(page, sel, "href")
            if href and "linkedin.com" not in href:
                return href

        return None

    def _extract_specialties(self, page: Page) -> list[str] | None:
        """Extract company specialties."""
        content = page.content()

        match = re.search(r'Specialties?[:\s]*([^<\n]+)', content, re.I)
        if match:
            specialties_text = match.group(1).strip()
            # Split by comma
            specialties = [s.strip() for s in specialties_text.split(",")]
            specialties = [s for s in specialties if s and len(s) < 50]
            return specialties[:10] if specialties else None

        return None

    def _extract_type(self, page: Page) -> str | None:
        """Extract company type (Public, Private, etc.)."""
        content = page.content()

        patterns = [
            r'Type[:\s]*(Public|Private|Partnership|Nonprofit|Self-[Ee]mployed|Government)',
            r'Company type[:\s]*(Public|Private|Partnership)',
        ]
        for pattern in patterns:
            match = re.search(pattern, content, re.I)
            if match:
                return match.group(1)

        return None

    def _extract_description(self, page: Page) -> str | None:
        """Extract company description."""
        selectors = [
            '[class*="org-about-us-organization-description"]',
            '[class*="about-us"] p',
            '[class*="description"]',
        ]
        for sel in selectors:
            text = self._safe_text(page, sel)
            if text and len(text) > 50:
                return text[:500] + "..." if len(text) > 500 else text

        return None
