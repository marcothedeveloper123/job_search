"""LinkedIn company profile extractor."""

import re
import sys
import time
from pathlib import Path

from playwright.sync_api import Page, sync_playwright

from scripts.research.base import BaseExtractor

# Use LinkedIn's persistent profile (same as job scraper)
LINKEDIN_PROFILE_DIR = Path(__file__).parent.parent.parent.parent / "data" / "linkedin_profile"

# JavaScript extraction for LinkedIn company pages
EXTRACTION_JS = """
() => {
    const result = {};
    const text = document.body.innerText || '';

    // Company name from h1
    const h1 = document.querySelector('h1');
    if (h1) {
        result.name = h1.innerText.trim();
    }

    // Look for "About" section data - LinkedIn uses dt/dd pairs
    const dts = document.querySelectorAll('dt');
    for (const dt of dts) {
        const label = dt.innerText.trim().toLowerCase();
        const dd = dt.nextElementSibling;
        if (!dd || dd.tagName !== 'DD') continue;
        const value = dd.innerText.trim();

        if (label.includes('website')) {
            const link = dd.querySelector('a');
            if (link) result.website = link.href;
        } else if (label.includes('industry')) {
            result.industry = value;
        } else if (label.includes('company size') || label.includes('employees')) {
            // Extract employee count - look for patterns like "501-1,000" or "1,001-5,000"
            const empMatch = value.match(/([\\d,]+(?:-[\\d,]+)?)/);
            if (empMatch) result.employees = empMatch[1];
        } else if (label.includes('headquarters')) {
            result.hq = value;
        } else if (label.includes('founded')) {
            const yearMatch = value.match(/(\\d{4})/);
            if (yearMatch) result.founded = yearMatch[1];
        } else if (label.includes('type')) {
            result.type = value;
        } else if (label.includes('specialties')) {
            result.specialties = value.split(',').map(s => s.trim()).filter(s => s);
        }
    }

    // Fallback: extract from page text if dt/dd didn't work
    if (!result.employees) {
        // Look for "X employees on LinkedIn" or "X,XXX employees"
        const empMatch = text.match(/([\\d,]+(?:-[\\d,]+)?)\\s+employees\\s+on\\s+LinkedIn/i) ||
                        text.match(/Company size\\s*([\\d,]+(?:-[\\d,]+)?)/i);
        if (empMatch) result.employees = empMatch[1];
    }

    if (!result.hq) {
        const hqMatch = text.match(/Headquarters?\\s*([^\\n]{5,50})/i);
        if (hqMatch) result.hq = hqMatch[1].trim();
    }

    if (!result.industry) {
        const indMatch = text.match(/Industry\\s*([^\\n]{5,50})/i);
        if (indMatch) result.industry = indMatch[1].trim();
    }

    if (!result.founded) {
        const foundedMatch = text.match(/Founded\\s*(\\d{4})/i);
        if (foundedMatch) result.founded = foundedMatch[1];
    }

    // Description - look for "Overview" or "About" section
    const descEl = document.querySelector('[class*="description"]') ||
                   document.querySelector('[class*="about-us"]');
    if (descEl) {
        const desc = descEl.innerText.trim();
        if (desc.length > 50) {
            result.description = desc.length > 500 ? desc.slice(0, 500) + '...' : desc;
        }
    }

    return result;
}
"""


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

        # Run JavaScript extraction
        try:
            extracted = page.evaluate(EXTRACTION_JS)
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
