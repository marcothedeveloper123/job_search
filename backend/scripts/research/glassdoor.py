"""Glassdoor company reviews extractor."""

import re

from playwright.sync_api import Page

from scripts.research.base import BaseExtractor


class GlassdoorExtractor(BaseExtractor):
    """Extract company review data from Glassdoor."""

    name = "glassdoor"

    def _run_extraction(self, page: Page) -> dict:
        """Extract review data from Glassdoor company page."""
        result = {
            "source": "glassdoor",
            "url": page.url,
        }

        # Overall rating (e.g., "4.2")
        rating = self._extract_rating(page)
        if rating:
            result["rating"] = rating

        # Total review count
        review_count = self._extract_review_count(page)
        if review_count:
            result["reviews"] = review_count

        # Ratings breakdown (culture, compensation, etc.)
        breakdown = self._extract_ratings_breakdown(page)
        if breakdown:
            result["ratings_breakdown"] = breakdown

        # CEO approval
        ceo = self._extract_ceo_approval(page)
        if ceo:
            result["ceo_approval"] = ceo

        # Recommend to friend percentage
        recommend = self._extract_recommend(page)
        if recommend:
            result["recommend_pct"] = recommend

        # Top pros and cons from reviews
        pros, cons = self._extract_pros_cons(page)
        if pros:
            result["pros"] = pros
        if cons:
            result["cons"] = cons

        # Interview difficulty
        interview = self._extract_interview_info(page)
        if interview:
            result["interview"] = interview

        return result

    def _extract_rating(self, page: Page) -> float | None:
        """Extract overall rating."""
        # Try various selectors Glassdoor uses
        selectors = [
            '[data-test="rating-info"] span',
            '.rating-headline .rating-num',
            '.v2__EIReviewsRatingsStylesV2__ratingNum',
            '[class*="ratingNum"]',
        ]
        for sel in selectors:
            text = self._safe_text(page, sel)
            if text:
                try:
                    return float(text)
                except ValueError:
                    continue
        return None

    def _extract_review_count(self, page: Page) -> int | None:
        """Extract total review count."""
        # Look for "X reviews" pattern
        selectors = [
            '[data-test="rating-info"]',
            '.rating-headline',
            '[class*="reviewCount"]',
        ]
        for sel in selectors:
            text = self._safe_text(page, sel)
            if text:
                match = re.search(r'([\d,]+)\s*reviews?', text, re.I)
                if match:
                    return int(match.group(1).replace(',', ''))
        return None

    def _extract_ratings_breakdown(self, page: Page) -> dict | None:
        """Extract breakdown ratings (culture, compensation, etc.)."""
        breakdown = {}

        # Look for specific rating categories
        categories = [
            ("culture", "Culture"),
            ("work_life_balance", "Work/Life Balance"),
            ("diversity", "Diversity"),
            ("compensation", "Compensation"),
            ("senior_management", "Senior Management"),
            ("career_opportunities", "Career Opportunities"),
        ]

        for key, label in categories:
            # Look for rating near the label text
            els = page.query_selector_all(f'//*[contains(text(), "{label}")]')
            for el in els:
                parent = el.evaluate_handle('el => el.closest("[class*=rating]") || el.parentElement')
                if parent:
                    text = parent.evaluate('el => el.textContent')
                    match = re.search(r'(\d\.?\d?)', text)
                    if match:
                        try:
                            breakdown[key] = float(match.group(1))
                        except ValueError:
                            pass

        return breakdown if breakdown else None

    def _extract_ceo_approval(self, page: Page) -> str | None:
        """Extract CEO approval rating."""
        # Look for "X% approve of CEO"
        selectors = [
            '[class*="ceo"] [class*="approval"]',
            '[data-test*="ceo"]',
        ]
        for sel in selectors:
            text = self._safe_text(page, sel)
            if text:
                match = re.search(r'(\d+)%', text)
                if match:
                    return f"{match.group(1)}%"

        # Try page-wide search
        content = page.content()
        match = re.search(r'(\d+)%\s*(?:approve|approval).{0,20}CEO', content, re.I)
        if match:
            return f"{match.group(1)}%"

        return None

    def _extract_recommend(self, page: Page) -> str | None:
        """Extract recommend to friend percentage."""
        content = page.content()
        match = re.search(r'(\d+)%\s*(?:would )?recommend', content, re.I)
        if match:
            return f"{match.group(1)}%"
        return None

    def _extract_pros_cons(self, page: Page) -> tuple[list[str], list[str]]:
        """Extract top pros and cons from reviews."""
        pros = []
        cons = []

        # Glassdoor review structure: each review has pros/cons sections
        reviews = page.query_selector_all('[class*="review"], [data-test*="review"]')[:5]

        for review in reviews:
            # Look for pros section
            pro_el = review.query_selector('[data-test="pros"], [class*="pros"]')
            if pro_el:
                text = pro_el.inner_text().strip()
                if text and len(text) > 10:
                    # Truncate long pros
                    pros.append(text[:200] + "..." if len(text) > 200 else text)

            # Look for cons section
            con_el = review.query_selector('[data-test="cons"], [class*="cons"]')
            if con_el:
                text = con_el.inner_text().strip()
                if text and len(text) > 10:
                    cons.append(text[:200] + "..." if len(text) > 200 else text)

        return pros[:5], cons[:5]

    def _extract_interview_info(self, page: Page) -> dict | None:
        """Extract interview difficulty and experience info."""
        result = {}

        # Interview difficulty (1-5 scale)
        difficulty_selectors = [
            '[class*="interviewDifficulty"]',
            '[data-test*="difficulty"]',
        ]
        for sel in difficulty_selectors:
            text = self._safe_text(page, sel)
            if text:
                match = re.search(r'(\d\.?\d?)', text)
                if match:
                    result["difficulty"] = float(match.group(1))
                    break

        # Experience breakdown (positive/neutral/negative)
        content = page.content()
        exp_match = re.search(r'(\d+)%\s*positive', content, re.I)
        if exp_match:
            result["positive_experience_pct"] = f"{exp_match.group(1)}%"

        return result if result else None
