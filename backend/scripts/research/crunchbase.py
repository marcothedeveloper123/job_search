"""Crunchbase company profile extractor."""

import re

from playwright.sync_api import Page

from scripts.research.base import BaseExtractor

# JavaScript extraction for Crunchbase
EXTRACTION_JS = """
() => {
    const result = {};
    const text = document.body.innerText || '';

    // Try JSON-LD structured data first
    const jsonLd = document.querySelectorAll('script[type="application/ld+json"]');
    for (const script of jsonLd) {
        try {
            const data = JSON.parse(script.textContent);
            if (data['@type'] === 'Organization') {
                if (data.name) result.name = data.name;
                if (data.description) result.description = data.description.slice(0, 500);
                if (data.foundingDate) result.founded = data.foundingDate;
                if (data.numberOfEmployees) {
                    result.employees = data.numberOfEmployees.value || data.numberOfEmployees;
                }
            }
        } catch (e) {}
    }

    // Extract funding info from visible text
    // Total funding
    const fundingPatterns = [
        /Total\\s+Funding[:\\s]*\\$?([\\d.,]+[BMK]?)/i,
        /(?:has\\s+)?raised[:\\s]*\\$?([\\d.,]+[BMK]?)/i,
        /\\$([\\d.,]+[BMK]?)\\s*(?:total\\s+)?(?:raised|funding)/i,
    ];
    for (const pattern of fundingPatterns) {
        const match = text.match(pattern);
        if (match) {
            result.funding_total = '$' + match[1].toUpperCase();
            break;
        }
    }

    // Funding stage
    const stageMatch = text.match(/(Series\\s+[A-Z]|Seed|Pre-Seed|IPO|Private\\s+Equity|Grant)/i);
    if (stageMatch) {
        result.funding_stage = stageMatch[1];
    }

    // Last round
    const lastRoundMatch = text.match(/(?:Latest|Last|Most\\s+Recent)\\s+(?:Funding|Round)[^$]*\\$([\\d.,]+[BMK]?)/i);
    if (lastRoundMatch) {
        result.last_round = '$' + lastRoundMatch[1].toUpperCase();
    }

    // Employee count
    if (!result.employees) {
        const empPatterns = [
            /([\\d,]+(?:-[\\d,]+)?)\\s*employees?/i,
            /Employees?[:\\s]*([\\d,]+(?:-[\\d,]+)?)/i,
            /Company\\s+Size[:\\s]*([\\d,]+(?:-[\\d,]+)?)/i,
        ];
        for (const pattern of empPatterns) {
            const match = text.match(pattern);
            if (match) {
                result.employees = match[1];
                break;
            }
        }
    }

    // Founded year
    if (!result.founded) {
        const foundedMatch = text.match(/Founded[:\\s]*(\\d{4})/i);
        if (foundedMatch) {
            result.founded = foundedMatch[1];
        }
    }

    // Headquarters
    const hqPatterns = [
        /Headquarters?[:\\s]*([^\\n,]{3,50})/i,
        /(?:Based|Located)\\s+in[:\\s]*([^\\n,]{3,50})/i,
        /HQ[:\\s]*([^\\n,]{3,50})/i,
    ];
    for (const pattern of hqPatterns) {
        const match = text.match(pattern);
        if (match) {
            const hq = match[1].trim();
            if (hq.length < 100 && !hq.includes('http')) {
                result.hq = hq;
                break;
            }
        }
    }

    // Description (if not from JSON-LD)
    if (!result.description) {
        // Look for "About" section content
        const aboutMatch = text.match(/About[\\n\\s]+([^\\n]{50,500})/);
        if (aboutMatch) {
            result.description = aboutMatch[1].trim();
        }
    }

    // Investors - look for investor names
    const investorSection = text.match(/(?:Investors?|Lead\\s+Investors?|Key\\s+Investors?)[:\\n\\s]+([^\\n]{20,500})/i);
    if (investorSection) {
        const investors = investorSection[1]
            .split(/[,\\n]/)
            .map(s => s.trim())
            .filter(s => s.length > 2 && s.length < 50)
            .slice(0, 5);
        if (investors.length > 0) {
            result.investors = investors;
        }
    }

    return result;
}
"""


class CrunchbaseExtractor(BaseExtractor):
    """Extract company funding and profile data from Crunchbase."""

    name = "crunchbase"

    def _run_extraction(self, page: Page) -> dict:
        """Extract funding and company data from Crunchbase."""
        result = {
            "source": "crunchbase",
            "url": page.url,
        }

        # Run JavaScript extraction in page context
        try:
            extracted = page.evaluate(EXTRACTION_JS)
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
