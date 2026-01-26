"""G2 software reviews extractor."""

import re

from playwright.sync_api import Page

from scripts.research.base import BaseExtractor
from scripts.research.remote import get_extractor_js


class G2Extractor(BaseExtractor):
    """Extract software review data from G2."""

    name = "g2"

    def _run_extraction(self, page: Page) -> dict:
        """Extract review data from G2 product page."""
        result = {
            "source": "g2",
            "url": page.url,
        }

        # Fetch and run remote JS extraction
        try:
            js_code = get_extractor_js("g2")
            extracted = page.evaluate(js_code)
            if extracted:
                result.update(extracted)
        except Exception:
            pass

        # Fallback: try regex on full page content
        if "rating" not in result:
            content = page.content()
            self._extract_from_html(content, result)

        return result

    def _extract_from_html(self, content: str, result: dict):
        """Fallback extraction from raw HTML."""
        # Rating from schema.org or data attributes
        rating_patterns = [
            r'ratingValue["\s:]+(\d\.\d)',
            r'"averageRating":\s*(\d\.\d)',
            r'data-rating="(\d\.\d)"',
        ]
        for pattern in rating_patterns:
            match = re.search(pattern, content)
            if match:
                result["rating"] = float(match.group(1))
                break

        # Review count
        review_patterns = [
            r'reviewCount["\s:]+(\d+)',
            r'"totalReviews":\s*(\d+)',
            r'(\d+)\s*(?:reviews|ratings)',
        ]
        for pattern in review_patterns:
            match = re.search(pattern, content, re.I)
            if match:
                result["reviews"] = int(match.group(1))
                break
