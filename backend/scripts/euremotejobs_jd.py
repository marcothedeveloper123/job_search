"""EU Remote Jobs Job Description Scraper using Playwright + JSON-LD."""

import html as html_lib
import re

from playwright.sync_api import sync_playwright

from scripts.scrape_utils import fix_html, fix_md, parse_iso_date, now_iso
from markdownify import markdownify as md


def _extract_slug(job_id_or_url: str) -> str:
    """Extract job slug from ID or URL."""
    if job_id_or_url.startswith("job_er_"):
        return job_id_or_url[7:]
    match = re.search(r"/job/([^/]+)/?", job_id_or_url)
    if match:
        return match.group(1)
    return job_id_or_url


# JS: Extract JobPosting JSON-LD from page (structured data for job description + date).
EXTRACT_JSONLD_JS = """
() => {
    const scripts = document.querySelectorAll('script[type="application/ld+json"]');
    for (const script of scripts) {
        try {
            const data = JSON.parse(script.textContent);
            // Single JobPosting object
            if (data['@type'] === 'JobPosting') return data;
            // Array of structured data - find JobPosting
            if (Array.isArray(data)) {
                const job = data.find(d => d['@type'] === 'JobPosting');
                if (job) return job;
            }
        } catch (e) {}
    }
    return null;
}
"""

DESC_SELECTORS = [".job_description", ".single_job_listing .content", "article .entry-content", ".job-description", "article"]


def _html_to_md_unescaped(html: str) -> str:
    """Convert HTML to markdown, unescaping HTML entities first (for JSON-LD)."""
    html = html_lib.unescape(html)
    html = fix_html(html)
    markdown = md(html, heading_style="ATX", bullets="-").strip()
    return fix_md(markdown)


def scrape_jd(job_id: str) -> dict:
    """Scrape job description from euremotejobs.com."""
    slug = _extract_slug(job_id)
    normalized_id = f"job_er_{slug}"
    url = job_id if job_id.startswith("http") else f"https://euremotejobs.com/job/{slug}/"

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            try:
                page.goto(url, wait_until="domcontentloaded", timeout=30000)
                page.wait_for_timeout(2000)

                jd_text, days_ago, posted = None, None, None

                # Primary: JSON-LD
                jsonld = page.evaluate(EXTRACT_JSONLD_JS)
                if jsonld:
                    desc_html = jsonld.get("description", "")
                    if desc_html:
                        jd_text = _html_to_md_unescaped(desc_html)
                    date_posted = jsonld.get("datePosted")
                    if date_posted:
                        days_ago = parse_iso_date(date_posted)
                        posted = date_posted.split("T")[0] if "T" in date_posted else date_posted

                # Fallback: DOM
                if not jd_text or len(jd_text) < 100:
                    for selector in DESC_SELECTORS:
                        el = page.query_selector(selector)
                        if el:
                            jd = _html_to_md_unescaped(el.inner_html())
                            if len(jd) > 100:
                                jd_text = jd
                                break

                if not jd_text or len(jd_text) < 100:
                    return {"status": "error", "error": "Could not find job description", "code": "SCRAPE_FAILED"}

                result = {"status": "ok", "job_id": normalized_id, "jd_text": jd_text, "url": page.url, "scraped_at": now_iso()}
                if days_ago is not None:
                    result["days_ago"] = days_ago
                if posted:
                    result["posted"] = posted
                return result
            finally:
                browser.close()
    except Exception as e:
        return {"status": "error", "error": str(e), "code": "SCRAPE_FAILED"}


def scrape_jds(job_ids: list[str]) -> dict:
    """Batch scrape job descriptions from euremotejobs.com."""
    if not job_ids:
        return {"status": "ok", "results": [], "succeeded": 0, "failed": 0}

    results, succeeded, failed = [], 0, 0

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            try:
                for job_id in job_ids:
                    slug = _extract_slug(job_id)
                    normalized_id = f"job_er_{slug}"
                    url = job_id if job_id.startswith("http") else f"https://euremotejobs.com/job/{slug}/"

                    try:
                        page.goto(url, wait_until="domcontentloaded", timeout=30000)
                        page.wait_for_timeout(2000)

                        jd_text, days_ago, posted = None, None, None

                        jsonld = page.evaluate(EXTRACT_JSONLD_JS)
                        if jsonld:
                            desc_html = jsonld.get("description", "")
                            if desc_html:
                                jd_text = _html_to_md_unescaped(desc_html)
                            date_posted = jsonld.get("datePosted")
                            if date_posted:
                                days_ago = parse_iso_date(date_posted)
                                posted = date_posted.split("T")[0] if "T" in date_posted else date_posted

                        if not jd_text or len(jd_text) < 100:
                            for selector in DESC_SELECTORS:
                                el = page.query_selector(selector)
                                if el:
                                    jd = _html_to_md_unescaped(el.inner_html())
                                    if len(jd) > 100:
                                        jd_text = jd
                                        break

                        if jd_text and len(jd_text) > 100:
                            item = {"job_id": normalized_id, "jd_text": jd_text, "url": page.url, "scraped_at": now_iso()}
                            if days_ago is not None:
                                item["days_ago"] = days_ago
                            if posted:
                                item["posted"] = posted
                            results.append(item)
                            succeeded += 1
                        else:
                            results.append({"job_id": normalized_id, "status": "error", "error": "JD not found"})
                            failed += 1

                        page.wait_for_timeout(1500)
                    except Exception as e:
                        results.append({"job_id": normalized_id, "status": "error", "error": str(e)})
                        failed += 1
            finally:
                browser.close()
    except Exception as e:
        return {"status": "error", "error": str(e), "code": "SCRAPE_FAILED"}

    return {"status": "ok", "results": results, "succeeded": succeeded, "failed": failed}
