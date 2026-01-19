"""Crunchbase company profile extractor."""

import re

from playwright.sync_api import Page

from scripts.research.base import BaseExtractor


class CrunchbaseExtractor(BaseExtractor):
    """Extract company funding and profile data from Crunchbase."""

    name = "crunchbase"

    def _run_extraction(self, page: Page) -> dict:
        """Extract funding and company data from Crunchbase."""
        result = {
            "source": "crunchbase",
            "url": page.url,
        }

        # Company description
        desc = self._extract_description(page)
        if desc:
            result["description"] = desc

        # Funding information
        funding = self._extract_funding(page)
        result.update(funding)

        # Key investors
        investors = self._extract_investors(page)
        if investors:
            result["investors"] = investors

        # Company details
        details = self._extract_details(page)
        result.update(details)

        return result

    def _extract_description(self, page: Page) -> str | None:
        """Extract company description."""
        selectors = [
            '[class*="description"]',
            '[data-test*="description"]',
            '.profile-section [class*="text"]',
        ]
        for sel in selectors:
            text = self._safe_text(page, sel)
            if text and len(text) > 20:
                # Truncate to reasonable length
                return text[:500] + "..." if len(text) > 500 else text
        return None

    def _extract_funding(self, page: Page) -> dict:
        """Extract funding information."""
        result = {}

        # Total funding
        content = page.content()

        # Look for "Total Funding" or similar
        funding_patterns = [
            r'Total Funding[:\s]*\$?([\d.,]+[BMK]?)',
            r'raised[:\s]*\$?([\d.,]+[BMK]?)',
            r'\$?([\d.,]+[BMK]?)\s*(?:total )?(?:raised|funding)',
        ]
        for pattern in funding_patterns:
            match = re.search(pattern, content, re.I)
            if match:
                result["funding_total"] = self._normalize_amount(match.group(1))
                break

        # Last funding round
        round_patterns = [
            r'(Series [A-Z]|Seed|Pre-Seed|IPO|Private Equity)',
            r'Latest Funding[:\s]*(Series [A-Z]|Seed)',
        ]
        for pattern in round_patterns:
            match = re.search(pattern, content)
            if match:
                result["funding_stage"] = match.group(1)
                break

        # Last round amount
        last_round_patterns = [
            r'(?:Latest|Last|Most Recent)[^$]*\$?([\d.,]+[BMK]?)',
        ]
        for pattern in last_round_patterns:
            match = re.search(pattern, content, re.I)
            if match:
                result["last_round"] = self._normalize_amount(match.group(1))
                break

        return result

    def _extract_investors(self, page: Page) -> list[str] | None:
        """Extract key investors."""
        investors = []

        # Look for investor links/names
        selectors = [
            '[class*="investor"] a',
            '[data-test*="investor"]',
            'a[href*="/organization/"][href*="investor"]',
        ]

        for sel in selectors:
            names = self._safe_all_text(page, sel, limit=5)
            investors.extend(names)

        # Dedupe and clean
        seen = set()
        clean = []
        for inv in investors:
            inv = inv.strip()
            if inv and inv.lower() not in seen and len(inv) > 2:
                seen.add(inv.lower())
                clean.append(inv)

        return clean[:5] if clean else None

    def _extract_details(self, page: Page) -> dict:
        """Extract company details (employees, founded, HQ, etc.)."""
        result = {}
        content = page.content()

        # Employee count
        emp_patterns = [
            r'Employees?[:\s]*([\d,]+(?:-[\d,]+)?)',
            r'([\d,]+(?:-[\d,]+)?)\s*employees?',
            r'([\d,]+-[\d,]+)\s*(?:total )?employees?',
        ]
        for pattern in emp_patterns:
            match = re.search(pattern, content, re.I)
            if match:
                result["employees"] = match.group(1)
                break

        # Founded year
        founded_patterns = [
            r'Founded[:\s]*(\d{4})',
            r'Founded in (\d{4})',
        ]
        for pattern in founded_patterns:
            match = re.search(pattern, content, re.I)
            if match:
                result["founded"] = match.group(1)
                break

        # Headquarters
        hq_patterns = [
            r'Headquarters?[:\s]*([^,\n]+)',
            r'HQ[:\s]*([^,\n]+)',
            r'Based in[:\s]*([^,\n]+)',
        ]
        for pattern in hq_patterns:
            match = re.search(pattern, content, re.I)
            if match:
                hq = match.group(1).strip()
                if len(hq) < 100:  # Sanity check
                    result["hq"] = hq
                break

        # Website
        website_selectors = [
            'a[href*="www."][class*="link"]',
            'a[data-test*="website"]',
        ]
        for sel in website_selectors:
            href = self._safe_attr(page, sel, "href")
            if href and "crunchbase" not in href:
                result["website"] = href
                break

        return result

    def _normalize_amount(self, amount: str) -> str:
        """Normalize funding amount to readable format."""
        amount = amount.strip().upper()
        # Already has B/M/K suffix
        if amount[-1] in "BMK":
            return "$" + amount
        # Try to parse and format
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
