"""G2 software reviews extractor."""

import re

from playwright.sync_api import Page

from scripts.research.base import BaseExtractor


class G2Extractor(BaseExtractor):
    """Extract software review data from G2."""

    name = "g2"

    def _run_extraction(self, page: Page) -> dict:
        """Extract review data from G2 product page."""
        result = {
            "source": "g2",
            "url": page.url,
        }

        # Product name
        name = self._extract_product_name(page)
        if name:
            result["product"] = name

        # Overall rating
        rating = self._extract_rating(page)
        if rating:
            result["rating"] = rating

        # Review count
        review_count = self._extract_review_count(page)
        if review_count:
            result["reviews"] = review_count

        # Category ranking
        ranking = self._extract_ranking(page)
        if ranking:
            result["ranking"] = ranking

        # Satisfaction ratings breakdown
        satisfaction = self._extract_satisfaction(page)
        if satisfaction:
            result["satisfaction"] = satisfaction

        # Top pros and cons
        pros, cons = self._extract_pros_cons(page)
        if pros:
            result["pros"] = pros
        if cons:
            result["cons"] = cons

        # Alternatives/competitors
        alternatives = self._extract_alternatives(page)
        if alternatives:
            result["alternatives"] = alternatives

        return result

    def _extract_product_name(self, page: Page) -> str | None:
        """Extract product name."""
        selectors = [
            'h1[itemprop="name"]',
            'h1[class*="product-name"]',
            'h1',
        ]
        for sel in selectors:
            text = self._safe_text(page, sel)
            if text and len(text) < 100:
                return text.strip()
        return None

    def _extract_rating(self, page: Page) -> float | None:
        """Extract overall rating."""
        selectors = [
            '[itemprop="ratingValue"]',
            '[class*="rating"] [class*="number"]',
            '[class*="star-rating"] span',
            '[data-test*="rating"]',
        ]
        for sel in selectors:
            text = self._safe_text(page, sel)
            if text:
                try:
                    rating = float(text)
                    if 0 <= rating <= 5:
                        return rating
                except ValueError:
                    continue

        # Try extracting from page content
        content = page.content()
        match = re.search(r'ratingValue["\s:]+(\d\.?\d?)', content)
        if match:
            try:
                return float(match.group(1))
            except ValueError:
                pass

        return None

    def _extract_review_count(self, page: Page) -> int | None:
        """Extract total review count."""
        selectors = [
            '[itemprop="reviewCount"]',
            '[class*="review-count"]',
            '[data-test*="review-count"]',
        ]
        for sel in selectors:
            text = self._safe_text(page, sel)
            if text:
                match = re.search(r'([\d,]+)', text)
                if match:
                    return int(match.group(1).replace(',', ''))

        # Try page-wide search
        content = page.content()
        match = re.search(r'reviewCount["\s:]+(\d+)', content)
        if match:
            return int(match.group(1))

        match = re.search(r'([\d,]+)\s*reviews?', content, re.I)
        if match:
            return int(match.group(1).replace(',', ''))

        return None

    def _extract_ranking(self, page: Page) -> dict | None:
        """Extract category ranking info."""
        result = {}

        # Look for "#X in Category" patterns
        content = page.content()
        rank_match = re.search(r'#(\d+)\s+in\s+([^<\n]+)', content, re.I)
        if rank_match:
            result["position"] = int(rank_match.group(1))
            result["category"] = rank_match.group(2).strip()

        # G2 badges/awards
        badges = self._safe_all_text(page, '[class*="badge"], [class*="award"]', limit=3)
        if badges:
            result["badges"] = badges

        return result if result else None

    def _extract_satisfaction(self, page: Page) -> dict | None:
        """Extract satisfaction breakdown (ease of use, support, etc.)."""
        result = {}

        categories = [
            ("ease_of_use", ["Ease of Use", "Usability"]),
            ("ease_of_setup", ["Ease of Setup", "Setup"]),
            ("ease_of_admin", ["Ease of Admin", "Administration"]),
            ("quality_of_support", ["Quality of Support", "Support"]),
            ("meets_requirements", ["Meets Requirements"]),
            ("product_direction", ["Product Direction"]),
        ]

        content = page.content()

        for key, labels in categories:
            for label in labels:
                # Look for "Label: X%" or "Label X.X/10"
                pattern = rf'{label}[:\s]*(\d+\.?\d?)(?:%|/10)?'
                match = re.search(pattern, content, re.I)
                if match:
                    try:
                        val = float(match.group(1))
                        # Normalize to percentage if out of 10
                        if val <= 10:
                            result[key] = f"{val}/10"
                        else:
                            result[key] = f"{val}%"
                        break
                    except ValueError:
                        continue

        return result if result else None

    def _extract_pros_cons(self, page: Page) -> tuple[list[str], list[str]]:
        """Extract top pros and cons from reviews."""
        pros = []
        cons = []

        # G2 review structure
        reviews = page.query_selector_all('[class*="review"], [itemprop="review"]')[:5]

        for review in reviews:
            # Look for "What do you like" section
            like_selectors = [
                '[class*="like"]',
                '[data-test*="like"]',
                ':text("What do you like")',
            ]
            for sel in like_selectors:
                el = review.query_selector(sel)
                if el:
                    text = el.inner_text().strip()
                    # Skip the header text itself
                    if text and len(text) > 20 and "what do you like" not in text.lower():
                        pros.append(text[:200] + "..." if len(text) > 200 else text)
                        break

            # Look for "What do you dislike" section
            dislike_selectors = [
                '[class*="dislike"]',
                '[data-test*="dislike"]',
                ':text("What do you dislike")',
            ]
            for sel in dislike_selectors:
                el = review.query_selector(sel)
                if el:
                    text = el.inner_text().strip()
                    if text and len(text) > 20 and "what do you dislike" not in text.lower():
                        cons.append(text[:200] + "..." if len(text) > 200 else text)
                        break

        return pros[:5], cons[:5]

    def _extract_alternatives(self, page: Page) -> list[str] | None:
        """Extract listed alternatives/competitors."""
        alternatives = []

        # G2 shows alternatives on product pages
        selectors = [
            '[class*="alternative"] a',
            '[class*="competitor"] a',
            '[data-test*="alternative"]',
            'a[href*="/products/"][href*="/competitors"]',
        ]

        for sel in selectors:
            names = self._safe_all_text(page, sel, limit=5)
            alternatives.extend(names)

        # Also look for "Compare" section
        compare_names = self._safe_all_text(page, '[class*="compare"] a', limit=5)
        alternatives.extend(compare_names)

        # Dedupe and clean
        seen = set()
        clean = []
        for alt in alternatives:
            alt = alt.strip()
            if alt and alt.lower() not in seen and len(alt) > 2 and len(alt) < 50:
                seen.add(alt.lower())
                clean.append(alt)

        return clean[:5] if clean else None
