"""LinkedIn Job Description Scraper API."""

import re
import time

from playwright.sync_api import sync_playwright

from scripts.linkedin_auth import PROFILE_DIR, _clear_lock
from scripts.scrape_utils import html_to_md, parse_days_ago_en, days_ago_to_iso, now_iso


def _extract_job_id(job_id_or_url: str) -> str:
    """Extract numeric job ID from URL or raw ID."""
    if job_id_or_url.startswith("job_li_"):
        return job_id_or_url[7:]
    if job_id_or_url.isdigit():
        return job_id_or_url
    match = re.search(r"/jobs/view/(\d+)", job_id_or_url)
    if match:
        return match.group(1)
    raise ValueError(f"Could not extract job ID from: {job_id_or_url}")


DESC_SELECTORS = [
    '[data-testid="expandable-text-box"]',
    ".show-more-less-html__markup",
    ".jobs-description__content",
    ".jobs-box__html-content",
    ".jobs-description-content__text",
    "[class*='jobs-description']",
    ".job-details-about-the-job-module__description",
    "article",
]


def _extract_days_ago(page) -> int | None:
    """Extract posting date from page."""
    top_card = page.query_selector(".job-details-jobs-unified-top-card__primary-description-container")
    if top_card:
        match = re.search(r"(\d+\s+(?:hour|day|week|month)s?\s+ago)", top_card.inner_text(), re.I)
        if match:
            return parse_days_ago_en(match.group(1))
    time_el = page.query_selector("strong:has-text('ago')")
    if time_el:
        match = re.search(r"(\d+\s+(?:hour|day|week|month)s?\s+ago)", time_el.inner_text(), re.I)
        if match:
            return parse_days_ago_en(match.group(1))
    return None


def _extract_jd(page) -> str | None:
    """Extract job description from page."""
    try:
        more_btn = page.query_selector('[data-testid="expandable-text-button"]')
        if more_btn and more_btn.is_visible():
            more_btn.click()
            time.sleep(0.5)
    except Exception:
        pass

    for selector in DESC_SELECTORS:
        el = page.query_selector(selector)
        if el:
            return html_to_md(el.inner_html())

    about = page.locator("h2:has-text('About the job')").first
    if about.count() > 0:
        sibling = about.locator("xpath=ancestor::div[1]/following-sibling::*[1]")
        if sibling.count() > 0:
            return html_to_md(sibling.inner_html())
    return None


def scrape_jd(job_id: str) -> dict:
    """Scrape job description from LinkedIn."""
    try:
        numeric_id = _extract_job_id(job_id)
    except ValueError as e:
        return {"status": "error", "error": str(e), "code": "INVALID_PARAM"}

    if not PROFILE_DIR.exists():
        return {"status": "error", "error": "Not authenticated. Run login() first.", "code": "AUTH_REQUIRED"}

    _clear_lock()
    normalized_id = f"job_li_{numeric_id}"
    url = f"https://www.linkedin.com/jobs/view/{numeric_id}/"

    try:
        with sync_playwright() as p:
            ctx = p.chromium.launch_persistent_context(str(PROFILE_DIR), headless=True, channel="chromium")
            page = ctx.new_page()
            try:
                page.goto(url, wait_until="domcontentloaded", timeout=30000)
                time.sleep(2)

                if "login" in page.url or "signup" in page.url:
                    return {"status": "error", "error": "Session expired. Run login() first.", "code": "AUTH_REQUIRED"}

                days_ago = _extract_days_ago(page)
                jd_text = _extract_jd(page)

                if not jd_text:
                    return {"status": "error", "error": "Could not find job description", "code": "SCRAPE_FAILED"}

                result = {"status": "ok", "job_id": normalized_id, "jd_text": jd_text, "scraped_at": now_iso()}
                if days_ago is not None:
                    result["days_ago"] = days_ago
                    result["posted"] = days_ago_to_iso(days_ago)
                return result
            finally:
                ctx.close()
    except Exception as e:
        return {"status": "error", "error": str(e), "code": "SCRAPE_FAILED"}


def scrape_jds(job_ids: list[str]) -> dict:
    """Batch scrape job descriptions from LinkedIn."""
    if not job_ids:
        return {"status": "ok", "results": [], "succeeded": 0, "failed": 0}
    if not PROFILE_DIR.exists():
        return {"status": "error", "error": "Not authenticated. Run login() first.", "code": "AUTH_REQUIRED"}

    _clear_lock()
    results, succeeded, failed = [], 0, 0

    try:
        with sync_playwright() as p:
            ctx = p.chromium.launch_persistent_context(str(PROFILE_DIR), headless=True, channel="chromium")
            page = ctx.new_page()
            try:
                for job_id in job_ids:
                    try:
                        numeric_id = _extract_job_id(job_id)
                    except ValueError as e:
                        results.append({"job_id": job_id, "status": "error", "error": str(e)})
                        failed += 1
                        continue

                    normalized_id = f"job_li_{numeric_id}"
                    url = f"https://www.linkedin.com/jobs/view/{numeric_id}/"

                    try:
                        page.goto(url, wait_until="domcontentloaded", timeout=30000)
                        time.sleep(2)

                        if "login" in page.url or "signup" in page.url:
                            results.append({"job_id": normalized_id, "status": "error", "error": "Session expired"})
                            failed += 1
                            break

                        days_ago = _extract_days_ago(page)
                        jd_text = _extract_jd(page)

                        if jd_text:
                            item = {"job_id": normalized_id, "jd_text": jd_text, "scraped_at": now_iso()}
                            if days_ago is not None:
                                item["days_ago"] = days_ago
                                item["posted"] = days_ago_to_iso(days_ago)
                            results.append(item)
                            succeeded += 1
                        else:
                            results.append({"job_id": normalized_id, "status": "error", "error": "JD not found"})
                            failed += 1

                        time.sleep(1)
                    except Exception as e:
                        results.append({"job_id": normalized_id, "status": "error", "error": str(e)})
                        failed += 1
            finally:
                ctx.close()
    except Exception as e:
        return {"status": "error", "error": str(e), "code": "SCRAPE_FAILED"}

    return {"status": "ok", "results": results, "succeeded": succeeded, "failed": failed}
