"""StartupJobs.cz Job Description Scraper API."""

import json
import re

import requests
from bs4 import BeautifulSoup

from scripts.scrape_utils import html_to_md, now_iso

USER_AGENT = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36"


def _extract_job_id(job_id_or_url: str) -> str:
    """Extract numeric job ID from URL or raw ID."""
    if job_id_or_url.startswith("job_sj_"):
        return job_id_or_url[7:]
    if job_id_or_url.isdigit():
        return job_id_or_url
    match = re.search(r"/nabidka/(\d+)", job_id_or_url)
    if match:
        return match.group(1)
    raise ValueError(f"Could not extract job ID from: {job_id_or_url}")


def _extract_nuxt_data(html: str) -> list | None:
    """Extract Nuxt payload from HTML."""
    match = re.search(r'<script[^>]*id="__NUXT_DATA__"[^>]*>([^<]+)</script>', html)
    if match:
        try:
            return json.loads(match.group(1))
        except json.JSONDecodeError:
            pass
    return None


DESC_SELECTORS = ["article", ".job-description", ".offer-description", '[class*="description"]', "main"]


def scrape_jd(job_id: str) -> dict:
    """Scrape job description from startupjobs.cz."""
    try:
        numeric_id = _extract_job_id(job_id)
    except ValueError as e:
        return {"status": "error", "error": str(e), "code": "INVALID_PARAM"}

    normalized_id = f"job_sj_{numeric_id}"
    url = job_id if job_id.startswith("http") else f"https://www.startupjobs.cz/nabidka/{numeric_id}"

    session = requests.Session()
    session.headers.update({"User-Agent": USER_AGENT, "Accept-Language": "cs,en;q=0.9"})

    try:
        response = session.get(url, timeout=30, allow_redirects=True)
        response.raise_for_status()

        soup = BeautifulSoup(response.text, "html.parser")
        jd_text = None

        for selector in DESC_SELECTORS:
            el = soup.select_one(selector)
            if el:
                for tag in el.find_all(['nav', 'header', 'footer', 'script', 'style']):
                    tag.decompose()
                jd_text = html_to_md(str(el))
                if len(jd_text) > 200:
                    break

        # Fallback: Nuxt payload
        if not jd_text or len(jd_text) < 200:
            nuxt = _extract_nuxt_data(response.text)
            if nuxt:
                for item in nuxt if isinstance(nuxt, list) else []:
                    if isinstance(item, str) and len(item) > 200 and '<' in item:
                        jd_text = html_to_md(item)
                        if len(jd_text) > 200:
                            break

        if not jd_text or len(jd_text) < 100:
            return {"status": "error", "error": "Could not find job description", "code": "SCRAPE_FAILED"}

        return {"status": "ok", "job_id": normalized_id, "jd_text": jd_text, "url": response.url, "scraped_at": now_iso()}

    except requests.RequestException as e:
        return {"status": "error", "error": str(e), "code": "SCRAPE_FAILED"}
    except Exception as e:
        return {"status": "error", "error": str(e), "code": "SCRAPE_FAILED"}


def scrape_jds(job_ids: list[str]) -> dict:
    """Batch scrape job descriptions from startupjobs.cz."""
    if not job_ids:
        return {"status": "ok", "results": [], "succeeded": 0, "failed": 0}

    results, succeeded, failed = [], 0, 0

    for job_id in job_ids:
        result = scrape_jd(job_id)
        if result.get("status") == "ok":
            results.append({
                "job_id": result["job_id"],
                "jd_text": result["jd_text"],
                "url": result.get("url"),
                "scraped_at": result["scraped_at"],
            })
            succeeded += 1
        else:
            results.append({"job_id": job_id, "status": "error", "error": result.get("error", "Unknown error")})
            failed += 1

    return {"status": "ok", "results": results, "succeeded": succeeded, "failed": failed}
