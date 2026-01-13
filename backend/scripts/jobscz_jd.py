"""Jobs.cz Job Description Scraper API using Playwright."""

import re

from playwright.sync_api import sync_playwright

from scripts.scrape_utils import html_to_md, parse_days_ago_cs, days_ago_to_iso, now_iso


def _extract_job_id(job_id_or_url: str) -> str:
    """Extract numeric job ID from URL or raw ID."""
    if job_id_or_url.startswith("job_cz_"):
        return job_id_or_url[7:]
    if job_id_or_url.isdigit():
        return job_id_or_url
    match = re.search(r"/(?:rpd|fp|pd)/(?:[^/]+/)?(\d+)", job_id_or_url)
    if match:
        return match.group(1)
    raise ValueError(f"Could not extract job ID from: {job_id_or_url}")


DESC_SELECTORS = [
    ".RichContent",
    ".cp-detail__content",
    ".c-detail__content",
    ".c-detail__description",
    '[data-test="job-detail-description"]',
    ".job-description",
    ".offer-description",
    "article",
]

DATE_SELECTORS = [
    '[data-test="job-detail-date"]',
    '.DetailHeader__date',
    '.JobDetailMeta__date',
    '[class*="date"]',
    '[class*="posted"]',
]


def _extract_days_ago(page) -> int | None:
    """Extract posting date from page."""
    for selector in DATE_SELECTORS:
        el = page.query_selector(selector)
        if el:
            days = parse_days_ago_cs(el.inner_text())
            if days is not None:
                return days
    # Fallback: search body for "zveřejněno: před X dny"
    body_text = page.inner_text("body")
    match = re.search(r"(?:zveřejněno|publikováno)[:\s]*(před[^,\n]+)", body_text, re.I)
    if match:
        return parse_days_ago_cs(match.group(1))
    return None


def _extract_jd(page) -> str | None:
    """Extract job description from page."""
    for selector in DESC_SELECTORS:
        el = page.query_selector(selector)
        if el:
            jd = html_to_md(el.inner_html())
            if len(jd) > 100:
                return jd
    return None


def scrape_jd(job_id: str) -> dict:
    """Scrape job description from jobs.cz."""
    try:
        numeric_id = _extract_job_id(job_id)
    except ValueError as e:
        return {"status": "error", "error": str(e), "code": "INVALID_PARAM"}

    normalized_id = f"job_cz_{numeric_id}"
    url = job_id if job_id.startswith("http") else f"https://www.jobs.cz/rpd/{numeric_id}/"

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            try:
                page.goto(url, wait_until="domcontentloaded", timeout=30000)
                page.wait_for_timeout(2000)

                days_ago = _extract_days_ago(page)
                jd_text = _extract_jd(page)

                if not jd_text or len(jd_text) < 100:
                    return {"status": "error", "error": "Could not find job description", "code": "SCRAPE_FAILED"}

                result = {"status": "ok", "job_id": normalized_id, "jd_text": jd_text, "url": page.url, "scraped_at": now_iso()}
                if days_ago is not None:
                    result["days_ago"] = days_ago
                    result["posted"] = days_ago_to_iso(days_ago)
                return result
            finally:
                browser.close()
    except Exception as e:
        return {"status": "error", "error": str(e), "code": "SCRAPE_FAILED"}


def scrape_jds(job_ids: list[str]) -> dict:
    """Batch scrape job descriptions from jobs.cz."""
    if not job_ids:
        return {"status": "ok", "results": [], "succeeded": 0, "failed": 0}

    results, succeeded, failed = [], 0, 0

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            try:
                for job_id in job_ids:
                    try:
                        numeric_id = _extract_job_id(job_id)
                    except ValueError as e:
                        results.append({"job_id": job_id, "status": "error", "error": str(e)})
                        failed += 1
                        continue

                    normalized_id = f"job_cz_{numeric_id}"
                    url = job_id if job_id.startswith("http") else f"https://www.jobs.cz/rpd/{numeric_id}/"

                    try:
                        page.goto(url, wait_until="domcontentloaded", timeout=30000)
                        page.wait_for_timeout(2000)

                        days_ago = _extract_days_ago(page)
                        jd_text = _extract_jd(page)

                        if jd_text and len(jd_text) > 100:
                            item = {"job_id": normalized_id, "jd_text": jd_text, "url": page.url, "scraped_at": now_iso()}
                            if days_ago is not None:
                                item["days_ago"] = days_ago
                                item["posted"] = days_ago_to_iso(days_ago)
                            results.append(item)
                            succeeded += 1
                        else:
                            results.append({"job_id": normalized_id, "status": "error", "error": "JD not found"})
                            failed += 1
                    except Exception as e:
                        results.append({"job_id": normalized_id, "status": "error", "error": str(e)})
                        failed += 1
            finally:
                browser.close()
    except Exception as e:
        return {"status": "error", "error": str(e), "code": "SCRAPE_FAILED"}

    return {"status": "ok", "results": results, "succeeded": succeeded, "failed": failed}
