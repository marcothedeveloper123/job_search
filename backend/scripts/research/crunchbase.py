"""Crunchbase company profile extractor."""

import re

from playwright.sync_api import Page

from scripts.research.base import BaseExtractor
from scripts.research.remote import get_extractor_js


class CrunchbaseExtractor(BaseExtractor):
    """Extract company funding and profile data from Crunchbase."""

    name = "crunchbase"

    def _run_extraction(self, page: Page) -> dict:
        """Extract funding and company data from Crunchbase."""
        result = {
            "source": "crunchbase",
            "url": page.url,
        }

        # Fetch and run remote JS extraction
        try:
            js_code = get_extractor_js("crunchbase")
            extracted = page.evaluate(js_code)
            if extracted:
                result.update(extracted)
        except Exception:
            pass

        # Fallback: try regex on full page content
        if "funding_total" not in result and "employees" not in result:
            content = page.content()
            self._extract_from_html(content, result)

        return result

    def _extract_from_html(self, content: str, result: dict):
        """Fallback extraction from raw HTML."""
        # Funding from data attributes or JSON
        funding_patterns = [
            r'"totalFundingAmount":\s*"?\$?([\\d.,]+[BMK]?)"?',
            r'"fundingTotal":\s*"?\$?([\\d.,]+[BMK]?)"?',
            r'data-funding="([\\d.,]+)"',
        ]
        for pattern in funding_patterns:
            match = re.search(pattern, content)
            if match:
                result["funding_total"] = self._normalize_amount(match.group(1))
                break

        # Employee count from meta/data
        emp_patterns = [
            r'"numberOfEmployees":\s*"?([\\d,]+(?:-[\\d,]+)?)"?',
            r'data-employees="([\\d,]+)"',
        ]
        for pattern in emp_patterns:
            match = re.search(pattern, content)
            if match:
                result["employees"] = match.group(1)
                break

    def _normalize_amount(self, amount: str) -> str:
        """Normalize funding amount to readable format."""
        amount = amount.strip().upper()
        if amount[-1] in "BMK":
            return "$" + amount
        try:
            num = float(amount.replace(",", ""))
            if num >= 1_000_000_000:
                return f"${num/1_000_000_000:.1f}B"
            elif num >= 1_000_000:
                return f"${num/1_000_000:.1f}M"
            elif num >= 1_000:
                return f"${num/1_000:.1f}K"
            else:
                return f"${num:.0f}"
        except ValueError:
            return amount
