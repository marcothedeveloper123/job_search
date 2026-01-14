"""Generic config-driven job board scraper.

Supports multiple engines:
- playwright: For JS-heavy sites (default)
- beautifulsoup: For simple HTML sites
- api: For JSON API endpoints

Usage:
    from scripts.generic_search import search_generic
    results = search_generic("indeed_nl", "product manager")
"""

import hashlib
import json
import re
import time
from pathlib import Path
from typing import Optional
from urllib.parse import urlencode

import requests
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright
from playwright_stealth import Stealth

from scripts.scraper_config import load_config, get_config_value
from scripts.scrape_utils import parse_days_ago_en, days_ago_to_iso, now_iso
from server.utils import categorize_level, has_ai_focus, level_rank

# Cache directory
SEARCH_CACHE_DIR = Path(__file__).parent.parent.parent / "data" / "runtime" / "searches"

USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)


def _generate_search_id(prefix: str) -> str:
    """Generate unique search ID with prefix."""
    return f"search_{prefix}_{hashlib.md5(now_iso().encode()).hexdigest()[:8]}"


def _build_search_url(config: dict, query: str, location: Optional[str] = None, page: int = 1) -> str:
    """Build search URL from config."""
    search_url = config.get("search_url", {})
    pattern = search_url.get("pattern", config.get("base_url", ""))

    # Replace placeholders
    url = pattern.replace("{query}", query.replace(" ", "+"))
    if location:
        url = url.replace("{location}", location.replace(" ", "+"))
    else:
        url = url.replace("{location}", "")

    # Handle pagination
    pagination = config.get("pagination", {})
    pag_type = pagination.get("type")

    if pag_type == "url_param" and page > 1:
        param = pagination.get("param", "page")
        increment = pagination.get("increment", 1)
        offset = (page - 1) * increment

        sep = "&" if "?" in url else "?"
        url = f"{url}{sep}{param}={offset}"

    return url


def _extract_job_id(url: str, config: dict) -> Optional[str]:
    """Extract job ID from URL using config regex."""
    pattern = get_config_value(config, "url_pattern.job_id_regex", r"/job/(\w+)")
    match = re.search(pattern, url)
    return match.group(1) if match else None


def _build_extraction_js(config: dict) -> str:
    """Build JS extraction code from config selectors."""
    # Check for custom JS first
    custom_js = config.get("extraction_js")
    if custom_js:
        return custom_js

    # Escape single quotes for JS strings
    def esc(s: str) -> str:
        return s.replace("'", "\\'")

    selectors = config.get("selectors", {})
    card = esc(selectors.get("card") or ".job-card")
    title = esc(selectors.get("title") or "a")
    company = esc(selectors.get("company") or ".company")
    location = esc(selectors.get("location") or ".location")
    posted = esc(selectors.get("posted") or "time")
    salary = esc(selectors.get("salary") or ".salary")

    # Support both URL regex and data attribute extraction
    job_id_attr = esc(get_config_value(config, "url_pattern.job_id_attr", ""))
    job_id_regex = get_config_value(config, "url_pattern.job_id_regex", "")

    # Build job ID extraction logic
    if job_id_attr:
        # Extract from data attribute (e.g., data-jk)
        job_id_extraction = f"""
        const jobId = titleEl.getAttribute('{job_id_attr}');
        if (!jobId) return;"""
    elif job_id_regex:
        # Extract from URL via regex - escape for JS regex literal
        job_id_regex_escaped = job_id_regex.replace("\\", "\\\\").replace("/", "\\/")
        job_id_extraction = f"""
        const href = titleEl.getAttribute('href') || '';
        const idMatch = href.match(/{job_id_regex_escaped}/);
        if (!idMatch) return;
        const jobId = idMatch[1];"""
    else:
        # Fallback: try data-id, then URL path
        job_id_extraction = """
        let jobId = titleEl.getAttribute('data-id') || titleEl.getAttribute('data-job-id');
        if (!jobId) {
            const href = titleEl.getAttribute('href') || '';
            const pathMatch = href.match(/\\/job[s]?\\/([\\w-]+)/);
            if (pathMatch) jobId = pathMatch[1];
        }
        if (!jobId) return;"""

    return f"""
() => {{
    const jobs = [];
    const cards = document.querySelectorAll('{card}');

    cards.forEach(card => {{
        // Find title link
        const titleEl = card.querySelector('{title}');
        if (!titleEl) return;
        {job_id_extraction}

        const href = titleEl.getAttribute('href') || '';
        const companyEl = card.querySelector('{company}');
        const locationEl = card.querySelector('{location}');
        const postedEl = card.querySelector('{posted}');
        const salaryEl = card.querySelector('{salary}');

        jobs.push({{
            job_id: jobId,
            title: titleEl.textContent.trim().split('\\n')[0].trim(),
            company: companyEl ? companyEl.textContent.trim() : '',
            location: locationEl ? locationEl.textContent.trim() : '',
            posted_text: postedEl ? postedEl.textContent.trim() : '',
            salary: salaryEl ? salaryEl.textContent.trim() : '',
            url: href.startsWith('http') ? href : window.location.origin + href
        }});
    }});

    return jobs;
}}
"""


def _scrape_playwright(
    config: dict,
    query: str,
    location: Optional[str] = None,
    max_pages: int = 3,
    collect_diagnostics: bool = False,
) -> dict:
    """Scrape using Playwright for JS-heavy sites."""
    all_jobs = []
    seen_ids = set()
    extraction_js = _build_extraction_js(config)
    delay_ms = config.get("delay_ms", 2000)
    cookie_dismiss = config.get("cookie_dismiss")
    selectors = config.get("selectors", {})

    diagnostics = {
        "page_title": None,
        "page_url": None,
        "selector_matches": {},
        "cookie_banner_detected": False,
        "cookie_banner_dismissed": False,
    }

    stealth = Stealth()
    with stealth.use_sync(sync_playwright()) as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        try:
            for page_num in range(1, max_pages + 1):
                url = _build_search_url(config, query, location, page_num)
                page.goto(url, wait_until="domcontentloaded", timeout=30000)
                time.sleep(delay_ms / 1000)

                # Collect diagnostics on first page
                if page_num == 1 and collect_diagnostics:
                    diagnostics["page_title"] = page.title()
                    diagnostics["page_url"] = page.url

                    # Count selector matches
                    for name, selector in selectors.items():
                        if selector:
                            try:
                                elements = page.query_selector_all(selector)
                                diagnostics["selector_matches"][name] = len(elements)
                            except Exception:
                                diagnostics["selector_matches"][name] = -1  # Invalid selector

                # Dismiss cookie consent if configured
                if cookie_dismiss and page_num == 1:
                    try:
                        btn = page.query_selector(cookie_dismiss)
                        if btn:
                            diagnostics["cookie_banner_detected"] = True
                            if btn.is_visible():
                                btn.click()
                                diagnostics["cookie_banner_dismissed"] = True
                                time.sleep(0.5)
                    except Exception:
                        pass  # Cookie banner may not appear

                # Handle pagination types that need interaction
                pagination = config.get("pagination", {})
                pag_type = pagination.get("type")

                if pag_type == "scroll":
                    # Scroll to load content
                    for _ in range(3):
                        page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                        time.sleep(1)

                elif pag_type == "load_more" and page_num > 1:
                    # Click load more button
                    selector = pagination.get("selector", "button.load-more")
                    btn = page.query_selector(selector)
                    if btn and btn.is_visible():
                        btn.click()
                        time.sleep(delay_ms / 1000)

                # Extract jobs
                raw_jobs = page.evaluate(extraction_js)

                for job in raw_jobs:
                    job_id = job.get("job_id")
                    if job_id and job_id not in seen_ids:
                        seen_ids.add(job_id)
                        all_jobs.append(job)

                # For button pagination, click next
                if pag_type == "button" and page_num < max_pages:
                    selector = pagination.get("selector", "button[aria-label='Next']")
                    btn = page.query_selector(selector)
                    if btn and btn.is_enabled():
                        btn.click()
                        time.sleep(delay_ms / 1000)
                    else:
                        break

        finally:
            browser.close()

    return {"jobs": all_jobs, "diagnostics": diagnostics}


def _scrape_beautifulsoup(
    config: dict,
    query: str,
    location: Optional[str] = None,
    max_pages: int = 3,
) -> list[dict]:
    """Scrape using BeautifulSoup for simple HTML sites."""
    all_jobs = []
    seen_ids = set()
    selectors = config.get("selectors", {})
    delay_ms = config.get("delay_ms", 1500)

    session = requests.Session()
    session.headers.update({
        "User-Agent": USER_AGENT,
        "Accept": "text/html,application/xhtml+xml",
        "Accept-Language": "en-US,en;q=0.9",
    })

    for page_num in range(1, max_pages + 1):
        url = _build_search_url(config, query, location, page_num)
        response = session.get(url, timeout=30)
        response.raise_for_status()

        soup = BeautifulSoup(response.text, "html.parser")
        cards = soup.select(selectors.get("card", ".job-card"))

        for card in cards:
            title_el = card.select_one(selectors.get("title", "a"))
            if not title_el:
                continue

            href = title_el.get("href", "")
            job_id = _extract_job_id(href, config)
            if not job_id or job_id in seen_ids:
                continue

            seen_ids.add(job_id)

            company_el = card.select_one(selectors.get("company", ".company"))
            location_el = card.select_one(selectors.get("location", ".location"))
            posted_el = card.select_one(selectors.get("posted", "time"))
            salary_el = card.select_one(selectors.get("salary", ".salary"))

            base_url = config.get("base_url", "")
            full_url = href if href.startswith("http") else base_url.rstrip("/") + href

            all_jobs.append({
                "job_id": job_id,
                "title": title_el.get_text(strip=True),
                "company": company_el.get_text(strip=True) if company_el else "",
                "location": location_el.get_text(strip=True) if location_el else "",
                "posted_text": posted_el.get_text(strip=True) if posted_el else "",
                "salary": salary_el.get_text(strip=True) if salary_el else "",
                "url": full_url,
            })

        # Check for more pages
        if page_num < max_pages:
            time.sleep(delay_ms / 1000)

    return all_jobs


def _scrape_api(
    config: dict,
    query: str,
    location: Optional[str] = None,
    max_pages: int = 3,
) -> list[dict]:
    """Scrape from JSON API endpoint."""
    all_jobs = []
    api_url = config.get("api_url", config.get("base_url", ""))
    api_fields = config.get("api_fields", {})
    delay_ms = config.get("delay_ms", 1500)

    session = requests.Session()
    session.headers.update({
        "User-Agent": USER_AGENT,
        "Accept": "application/json",
    })

    # Build API params
    params = {"q": query}
    if location:
        params["location"] = location

    for page_num in range(1, max_pages + 1):
        params["page"] = page_num
        response = session.get(api_url, params=params, timeout=30)
        response.raise_for_status()
        data = response.json()

        # Handle different response formats
        if isinstance(data, list):
            items = data
        elif isinstance(data, dict):
            items = data.get("results", data.get("jobs", data.get("member", [])))
        else:
            items = []

        for item in items:
            # Map API fields to standard format
            job_id = _get_nested(item, api_fields.get("job_id", "id"))
            title = _get_nested(item, api_fields.get("title", "title"))
            company = _get_nested(item, api_fields.get("company", "company"))
            loc = _get_nested(item, api_fields.get("location", "location"))
            url = _get_nested(item, api_fields.get("url", "url"))
            posted = _get_nested(item, api_fields.get("posted", "posted"))
            salary_min = _get_nested(item, api_fields.get("salary_min", ""))
            salary_max = _get_nested(item, api_fields.get("salary_max", ""))

            salary = None
            if salary_min and salary_max:
                salary = f"{salary_min} - {salary_max}"
            elif salary_min:
                salary = f"from {salary_min}"

            all_jobs.append({
                "job_id": str(job_id),
                "title": str(title) if title else "",
                "company": str(company) if company else "",
                "location": str(loc) if loc else "",
                "posted_text": str(posted) if posted else "",
                "salary": salary,
                "url": str(url) if url else "",
            })

        if len(items) == 0:
            break

        if page_num < max_pages:
            time.sleep(delay_ms / 1000)

    return all_jobs


def _get_nested(obj: dict, path: str):
    """Get nested value from dict using dot notation or array access."""
    if not path:
        return None

    parts = re.split(r'\.|\[|\]', path)
    parts = [p for p in parts if p]

    value = obj
    for part in parts:
        if value is None:
            return None
        if isinstance(value, dict):
            value = value.get(part)
        elif isinstance(value, list) and part.isdigit():
            idx = int(part)
            value = value[idx] if idx < len(value) else None
        else:
            return None

    return value


def search_generic(
    name: str,
    query: str,
    location: Optional[str] = None,
    max_pages: int = 3,
    exclude_locations: Optional[list[str]] = None,
    exclude_companies: Optional[list[str]] = None,
    min_level: Optional[str] = None,
    ai_only: bool = False,
    collect_diagnostics: bool = False,
) -> dict:
    """
    Search a job board using config-driven scraping.

    Args:
        name: Scraper name (matches config file name without .json)
        query: Search keywords
        location: Location filter (optional)
        max_pages: Max pages to scrape
        exclude_locations: Filter out jobs with these strings
        exclude_companies: Filter out these companies
        min_level: Minimum level filter
        ai_only: Only AI-focused jobs
        collect_diagnostics: Return page info and selector match counts

    Returns:
        {"status": "ok", "jobs": [...], "diagnostics": {...}, ...}
    """
    config = load_config(name)
    if config is None:
        return {"status": "error", "error": f"No config found for '{name}'", "code": "CONFIG_NOT_FOUND"}

    SEARCH_CACHE_DIR.mkdir(parents=True, exist_ok=True)

    engine = config.get("engine", "playwright")
    id_prefix = config.get("id_prefix", f"{name[:2]}_")
    diagnostics = None

    try:
        if engine == "playwright":
            result = _scrape_playwright(config, query, location, max_pages, collect_diagnostics)
            raw_jobs = result["jobs"]
            diagnostics = result.get("diagnostics")
        elif engine == "beautifulsoup":
            raw_jobs = _scrape_beautifulsoup(config, query, location, max_pages)
        elif engine == "api":
            raw_jobs = _scrape_api(config, query, location, max_pages)
        else:
            return {"status": "error", "error": f"Unknown engine: {engine}", "code": "INVALID_ENGINE"}
    except Exception as e:
        return {"status": "error", "error": str(e), "code": "SCRAPE_FAILED"}

    # Enrich jobs
    enriched_jobs = []
    for job in raw_jobs:
        days_ago = parse_days_ago_en(job.get("posted_text", ""))
        posted = days_ago_to_iso(days_ago) if days_ago is not None else None
        title = job.get("title", "")

        enriched_jobs.append({
            "job_id": f"job_{id_prefix}{job['job_id']}",
            "title": title,
            "company": job.get("company"),
            "location": job.get("location"),
            "salary": job.get("salary") or None,
            "url": job.get("url"),
            "source": name,
            "level": categorize_level(title),
            "ai_focus": has_ai_focus(title),
            "posted": posted,
            "days_ago": days_ago,
        })

    # Apply filters
    filtered_out = 0
    filtered_jobs = []

    for job in enriched_jobs:
        if exclude_locations:
            loc = (job.get("location") or "").lower()
            if any(ex.lower() in loc for ex in exclude_locations):
                filtered_out += 1
                continue

        if exclude_companies:
            company = (job.get("company") or "").lower()
            if any(ex.lower() in company for ex in exclude_companies):
                filtered_out += 1
                continue

        if min_level:
            job_rank = level_rank(job["level"])
            min_rank = level_rank(min_level)
            if job_rank < min_rank:
                filtered_out += 1
                continue

        if ai_only and not job.get("ai_focus"):
            filtered_out += 1
            continue

        filtered_jobs.append(job)

    # Cache results
    search_id = _generate_search_id(id_prefix.rstrip("_"))
    cache_data = {
        "search_id": search_id,
        "scraper": name,
        "query": query,
        "location": location,
        "jobs": filtered_jobs,
        "all_jobs": enriched_jobs,
        "created_at": now_iso(),
    }

    cache_file = SEARCH_CACHE_DIR / f"{search_id}.json"
    cache_file.write_text(json.dumps(cache_data, indent=2))

    result = {
        "status": "ok",
        "search_id": search_id,
        "jobs": filtered_jobs,
        "job_count": len(filtered_jobs),
        "total_scraped": len(enriched_jobs),
        "filtered_out": filtered_out,
    }

    if diagnostics:
        result["diagnostics"] = diagnostics

    return result
