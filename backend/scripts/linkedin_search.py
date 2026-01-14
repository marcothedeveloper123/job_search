"""LinkedIn Search API with region presets and filtering.

Config-driven with fallback to hardcoded defaults.
Edit data/scrapers/linkedin.json to update selectors without code changes.
"""

import hashlib
import json
import time
from pathlib import Path
from typing import Optional
from urllib.parse import urlencode

from playwright.sync_api import sync_playwright

from scripts.linkedin_auth import PROFILE_DIR, _clear_lock
from scripts.scrape_utils import parse_days_ago_en, days_ago_to_iso, now_iso
from scripts.scraper_config import (
    load_config, get_selector, get_config_value, build_extraction_js
)
from server.utils import categorize_level, has_ai_focus, level_rank

# Search results cache directory
SEARCH_CACHE_DIR = Path(__file__).parent.parent.parent / "data" / "runtime" / "searches"

# Load config (None if missing or invalid - will use hardcoded defaults)
_config = load_config("linkedin")

# Config-driven selectors with hardcoded fallbacks
CARD_SELECTOR = get_selector(_config, "card", ".job-card-container")
NEXT_PAGE_SELECTOR = get_config_value(
    _config, "pagination.selector", 'button[aria-label="View next page"]'
)

# LinkedIn GeoId codes for regions/countries
# These map directly to LinkedIn's geoId URL parameter
LINKEDIN_GEO_IDS = {
    "europe": "100506914",
    "czechia": "104508036",
    "prague": "106978326",  # City-level for f_PP (preferred location)
    "netherlands": "102890719",
    "germany": "101282230",
    "france": "105015875",
    "spain": "105646813",
    "italy": "103350119",
    "poland": "105072130",
    "portugal": "100364837",
    "ireland": "104738515",
    "belgium": "100565514",
    "switzerland": "106693272",
    "sweden": "105117694",
}

# Region presets using geoId params (not location string)
REGION_PRESETS = {
    "eu_remote": {"geo_id": "100506914", "remote": True},  # Europe-wide
    "prague": {"geo_id": "100506914", "f_PP": "106978326", "distance": 25},  # EU + Prague preferred
    "netherlands": {"geo_id": "102890719", "remote": True},
    "germany": {"geo_id": "101282230", "remote": True},
    "spain": {"geo_id": "105646813", "remote": True},
    "france": {"geo_id": "105015875", "remote": True},
    "italy": {"geo_id": "103350119", "remote": True},
    "poland": {"geo_id": "105072130", "remote": True},
    "ireland": {"geo_id": "104738515", "remote": True},
    "portugal": {"geo_id": "100364837", "remote": True},
    "czechia": {"geo_id": "104508036", "remote": True},
}

# JS: Extract job listings from search results page.
# Selectors: .job-card-container for cards, artdeco-entity-lockup for metadata.
# Also extracts posting date from <time> or footer items for "X days ago" text.
EXTRACTION_JS = """
() => {
    const jobs = [];
    const cards = document.querySelectorAll('.job-card-container');

    cards.forEach(card => {
        const link = card.querySelector('a[href*="/jobs/view/"]');
        if (!link) return;

        const href = link.getAttribute('href');
        const jobIdMatch = href.match(/\\/jobs\\/view\\/(\\d+)/);
        if (!jobIdMatch) return;

        const title = link.textContent.trim().split('\\n')[0].replace(' with verification', '').trim();
        const companyEl = card.querySelector('.artdeco-entity-lockup__subtitle');
        const company = companyEl ? companyEl.textContent.trim() : '';
        const locationEl = card.querySelector('.artdeco-entity-lockup__caption');
        const location = locationEl ? locationEl.textContent.trim() : '';

        // Extract posting date - try multiple selectors
        let postedText = '';
        const timeEl = card.querySelector('time');
        if (timeEl) {
            postedText = timeEl.textContent.trim();
        } else {
            // Fallback: look for footer items containing time-related text
            const footerItems = card.querySelectorAll('.job-card-container__footer-item, .job-card-container__listed-time');
            for (const item of footerItems) {
                const text = item.textContent.trim().toLowerCase();
                if (text.includes('ago') || text.includes('hour') || text.includes('day') || text.includes('week') || text.includes('month')) {
                    postedText = item.textContent.trim();
                    break;
                }
            }
        }

        jobs.push({
            job_id: jobIdMatch[1],
            title,
            company,
            location,
            posted_text: postedText,
            url: `https://www.linkedin.com/jobs/view/${jobIdMatch[1]}/`,
        });
    });

    return jobs;
}
"""

# Use config-driven extraction JS if available, otherwise hardcoded default
_EXTRACTION_JS = build_extraction_js(_config, EXTRACTION_JS)

# JS: Scroll the job list to trigger lazy loading.
SCROLL_JS = """
() => {
    const containers = document.querySelectorAll('*');
    for (let el of containers) {
        // Find scrollable element containing job cards
        if (el.scrollHeight > el.clientHeight && el.clientHeight > 100) {
            if (el.querySelector('.job-card-container') || el.querySelector('[data-job-id]') || el.querySelector('.jobs-search-results__list-item')) {
                el.scrollTo(0, el.scrollHeight);
                return true;
            }
        }
    }
    return false;
}
"""

# JS: Alternate extraction for recommended/collections pages.
# LinkedIn uses different selectors on /jobs/collections/recommended/ vs search.
EXTRACTION_JS_ALT = """
() => {
    const jobs = [];

    // Try multiple selector patterns
    const selectors = [
        '.jobs-search-results__list-item',
        '[data-job-id]',
        '.job-card-list__entity-lockup',
        '.jobs-job-board-list__item',
        'li[class*="job"]'
    ];

    let cards = [];
    for (const sel of selectors) {
        cards = document.querySelectorAll(sel);
        if (cards.length > 0) break;
    }

    cards.forEach(card => {
        // Find job link
        const link = card.querySelector('a[href*="/jobs/view/"]');
        if (!link) return;

        const href = link.getAttribute('href');
        const jobIdMatch = href.match(/\\/jobs\\/view\\/(\\d+)/);
        if (!jobIdMatch) return;

        // Try multiple title selectors
        let title = '';
        const titleEl = card.querySelector('.job-card-list__title, .artdeco-entity-lockup__title, [class*="title"]');
        if (titleEl) {
            title = titleEl.textContent.trim().split('\\n')[0].replace(' with verification', '').trim();
        } else {
            title = link.textContent.trim().split('\\n')[0].replace(' with verification', '').trim();
        }

        // Try multiple company selectors
        let company = '';
        const companyEl = card.querySelector('.job-card-container__primary-description, .artdeco-entity-lockup__subtitle, [class*="company"], [class*="subtitle"]');
        if (companyEl) company = companyEl.textContent.trim();

        // Try multiple location selectors
        let location = '';
        const locationEl = card.querySelector('.job-card-container__metadata-item, .artdeco-entity-lockup__caption, [class*="location"], [class*="caption"]');
        if (locationEl) location = locationEl.textContent.trim();

        jobs.push({
            job_id: jobIdMatch[1],
            title,
            company,
            location,
            posted_text: '',
            url: `https://www.linkedin.com/jobs/view/${jobIdMatch[1]}/`,
        });
    });

    return jobs;
}
"""


def _generate_search_id() -> str:
    """Generate unique search ID."""
    return f"search_{hashlib.md5(now_iso().encode()).hexdigest()[:8]}"


def _build_search_url(
    query: str,
    geo_id: Optional[str] = None,
    f_PP: Optional[str] = None,
    distance: Optional[int] = None,
    remote: Optional[bool] = None,
    days: int = 30,
) -> str:
    """
    Build LinkedIn job search URL using proper LinkedIn parameters.

    Args:
        query: Search keywords
        geo_id: LinkedIn geoId for region/country (e.g., "100506914" for Europe)
        f_PP: Preferred posting location geoId (e.g., "106978326" for Prague)
        distance: Search radius in km from preferred location
        remote: Filter for remote jobs (f_WT=2)
        days: Posted within N days
    """
    params = {
        "keywords": query,
        "f_TPR": f"r{days * 24 * 60 * 60}" if days else "",  # Time posted filter
    }

    if geo_id:
        params["geoId"] = geo_id

    if f_PP:
        params["f_PP"] = f_PP

    if distance:
        params["distance"] = str(distance)

    if remote:
        params["f_WT"] = "2"  # Remote filter

    base_url = "https://www.linkedin.com/jobs/search/?"
    return base_url + urlencode({k: v for k, v in params.items() if v})


def search_linkedin(
    query: str,
    region: Optional[str] = None,
    geo_id: Optional[str] = None,
    f_PP: Optional[str] = None,
    distance: Optional[int] = None,
    remote: Optional[bool] = None,
    days: int = 30,
    max_pages: int = 3,
    exclude_locations: Optional[list[str]] = None,
    exclude_companies: Optional[list[str]] = None,
    min_level: Optional[str] = None,
    ai_only: bool = False,
) -> dict:
    """
    Search LinkedIn jobs with filtering and region presets.

    Args:
        query: Search keywords
        region: Preset name (eu_remote, prague, netherlands, etc.)
        geo_id: LinkedIn geoId override (e.g., "100506914" for Europe)
        f_PP: Preferred posting location geoId override
        distance: Search radius in km from preferred location
        remote: Remote filter override
        days: Posted within N days
        max_pages: Pages to scrape (default 3)
        exclude_locations: Filter out jobs with these strings in location
        exclude_companies: Filter out these companies
        min_level: Minimum level (senior, staff, principal, leadership)
        ai_only: Only return jobs where ai_focus=True

    Returns:
        {"status": "ok", "search_id": "...", "jobs": [...], ...}
    """
    SEARCH_CACHE_DIR.mkdir(parents=True, exist_ok=True)

    # Resolve region preset or use direct params
    effective_geo_id = geo_id
    effective_f_PP = f_PP
    effective_distance = distance
    effective_remote = remote

    if not geo_id and region and region in REGION_PRESETS:
        preset = REGION_PRESETS[region]
        effective_geo_id = preset.get("geo_id")
        if f_PP is None:
            effective_f_PP = preset.get("f_PP")
        if distance is None:
            effective_distance = preset.get("distance")
        if remote is None:
            effective_remote = preset.get("remote")

    # Build search URL with geoId params
    url = _build_search_url(
        query=query,
        geo_id=effective_geo_id,
        f_PP=effective_f_PP,
        distance=effective_distance,
        remote=effective_remote,
        days=days,
    )

    # Check auth
    if not PROFILE_DIR.exists():
        return {"status": "error", "error": "Not authenticated. Run login() first.", "code": "AUTH_REQUIRED"}

    _clear_lock()

    all_jobs = []
    seen_ids = set()
    pages_fetched = 0

    try:
        with sync_playwright() as p:
            context = p.chromium.launch_persistent_context(
                str(PROFILE_DIR),
                headless=True,
                channel="chromium",
            )
            page = context.new_page()

            try:
                page.goto(url, wait_until="domcontentloaded", timeout=30000)
                time.sleep(2)

                # Check if logged in
                if "login" in page.url or "signup" in page.url:
                    context.close()
                    return {"status": "error", "error": "Session expired. Run login() first.", "code": "AUTH_REQUIRED"}

                # Check for rate limiting / verification page
                if "challenge" in page.url or "checkpoint" in page.url:
                    context.close()
                    return {"status": "error", "error": "LinkedIn requires verification. Try again later or re-login.", "code": "RATE_LIMITED"}

                for page_num in range(max_pages):
                    # Scroll to load all jobs
                    for _ in range(5):
                        scrolled = page.evaluate(SCROLL_JS)
                        if not scrolled:
                            break
                        time.sleep(1)

                    # Extract jobs
                    raw_jobs = page.evaluate(_EXTRACTION_JS)
                    pages_fetched += 1

                    for job in raw_jobs:
                        if job["job_id"] not in seen_ids:
                            seen_ids.add(job["job_id"])
                            all_jobs.append(job)

                    # Try next page
                    next_btn = page.query_selector(NEXT_PAGE_SELECTOR)
                    if next_btn and next_btn.is_enabled():
                        next_btn.click()
                        time.sleep(2)
                    else:
                        break

            finally:
                context.close()

    except Exception as e:
        return {"status": "error", "error": str(e), "code": "SCRAPE_FAILED"}

    # Enrich with computed fields
    enriched_jobs = []
    for job in all_jobs:
        # Parse posting date
        days_ago = parse_days_ago_en(job.get("posted_text", ""))
        posted = days_ago_to_iso(days_ago) if days_ago is not None else None

        enriched_jobs.append({
            "job_id": f"job_li_{job['job_id']}",
            "title": job["title"],
            "company": job["company"],
            "location": job["location"],
            "salary": None,  # LinkedIn doesn't show salary in search
            "url": job["url"],
            "source": "linkedin",
            "level": categorize_level(job["title"]),
            "ai_focus": has_ai_focus(job["title"]),
            "posted": posted,
            "days_ago": days_ago,
        })

    # Apply filters
    filtered_out = 0
    filtered_jobs = []

    for job in enriched_jobs:
        # Exclude locations
        if exclude_locations:
            loc = (job.get("location") or "").lower()
            if any(ex.lower() in loc for ex in exclude_locations):
                filtered_out += 1
                continue

        # Exclude companies
        if exclude_companies:
            company = (job.get("company") or "").lower()
            if any(ex.lower() in company for ex in exclude_companies):
                filtered_out += 1
                continue

        # Min level filter
        if min_level:
            job_rank = level_rank(job["level"])
            min_rank = level_rank(min_level)
            if job_rank < min_rank:
                filtered_out += 1
                continue

        # AI only filter
        if ai_only and not job.get("ai_focus"):
            filtered_out += 1
            continue

        filtered_jobs.append(job)

    # Generate search ID and cache results
    search_id = _generate_search_id()
    cache_data = {
        "search_id": search_id,
        "query": query,
        "region": region,
        "geo_id": effective_geo_id,
        "f_PP": effective_f_PP,
        "distance": effective_distance,
        "remote": effective_remote,
        "days": days,
        "max_pages": max_pages,
        "filters": {
            "exclude_locations": exclude_locations,
            "exclude_companies": exclude_companies,
            "min_level": min_level,
            "ai_only": ai_only,
        },
        "jobs": filtered_jobs,
        "all_jobs": enriched_jobs,  # Unfiltered for later retrieval
        "created_at": now_iso(),
    }

    cache_file = SEARCH_CACHE_DIR / f"{search_id}.json"
    cache_file.write_text(json.dumps(cache_data, indent=2))

    return {
        "status": "ok",
        "search_id": search_id,
        "jobs": filtered_jobs,
        "job_count": len(filtered_jobs),
        "pages_fetched": pages_fetched,
        "pages_requested": max_pages,
        "filtered_out": filtered_out,
    }


def get_search_results(search_id: str) -> dict:
    """
    Retrieve cached search results by search_id.

    Args:
        search_id: Search ID from previous search

    Returns:
        Same structure as search_linkedin()
    """
    cache_file = SEARCH_CACHE_DIR / f"{search_id}.json"
    if not cache_file.exists():
        return {"status": "error", "error": f"Search {search_id} not found", "code": "JOB_NOT_FOUND"}

    try:
        data = json.loads(cache_file.read_text())
        return {
            "status": "ok",
            "search_id": data["search_id"],
            "jobs": data["jobs"],
            "job_count": len(data["jobs"]),
            "all_jobs_count": len(data.get("all_jobs", [])),
            "created_at": data.get("created_at"),
        }
    except Exception as e:
        return {"status": "error", "error": str(e), "code": "SCRAPE_FAILED"}


def scrape_top_picks(
    exclude_locations: Optional[list[str]] = None,
    exclude_companies: Optional[list[str]] = None,
    min_level: Optional[str] = None,
    ai_only: bool = False,
) -> dict:
    """
    Scrape LinkedIn's personalized "Top job picks for you".

    This supplements search_linkedin() by letting LinkedIn's algorithm
    surface jobs based on your profile, rather than explicit queries.

    Args:
        exclude_locations: Filter out jobs with these strings in location
        exclude_companies: Filter out these companies
        min_level: Minimum level (senior, staff, principal, leadership)
        ai_only: Only return jobs where ai_focus=True

    Returns:
        {"status": "ok", "jobs": [...], ...}
    """
    if not PROFILE_DIR.exists():
        return {"status": "error", "error": "Not authenticated. Run login() first.", "code": "AUTH_REQUIRED"}

    _clear_lock()
    all_jobs = []
    seen_ids = set()

    try:
        with sync_playwright() as p:
            context = p.chromium.launch_persistent_context(
                str(PROFILE_DIR),
                headless=True,
                channel="chromium",
            )
            page = context.new_page()

            try:
                # Go to LinkedIn Jobs home
                page.goto("https://www.linkedin.com/jobs/", wait_until="domcontentloaded", timeout=30000)
                time.sleep(2)

                # Check if logged in
                if "login" in page.url or "signup" in page.url:
                    context.close()
                    return {"status": "error", "error": "Session expired. Run login() first.", "code": "AUTH_REQUIRED"}

                if "challenge" in page.url or "checkpoint" in page.url:
                    context.close()
                    return {"status": "error", "error": "LinkedIn requires verification.", "code": "RATE_LIMITED"}

                # Navigate directly to recommended jobs page
                page.goto("https://www.linkedin.com/jobs/collections/recommended/", wait_until="domcontentloaded", timeout=30000)
                time.sleep(5)

                # Scroll to load all jobs
                for _ in range(8):
                    scrolled = page.evaluate(SCROLL_JS)
                    if not scrolled:
                        break
                    time.sleep(1)

                # Extract jobs - try multiple selectors
                raw_jobs = page.evaluate(_EXTRACTION_JS)

                # If no jobs found, try alternate selectors for recommended page
                if not raw_jobs:
                    raw_jobs = page.evaluate(EXTRACTION_JS_ALT)

                # Debug: save screenshot if no jobs found
                if not raw_jobs:
                    debug_dir = Path(__file__).parent.parent.parent / "data" / "runtime" / "debug"
                    debug_dir.mkdir(parents=True, exist_ok=True)
                    page.screenshot(path=str(debug_dir / "top_picks_debug.png"))

                for job in raw_jobs:
                    if job["job_id"] not in seen_ids:
                        seen_ids.add(job["job_id"])
                        all_jobs.append(job)

            finally:
                context.close()

    except Exception as e:
        return {"status": "error", "error": str(e), "code": "SCRAPE_FAILED"}

    # Enrich with computed fields (same as search_linkedin)
    enriched_jobs = []
    for job in all_jobs:
        days_ago = parse_days_ago_en(job.get("posted_text", ""))
        posted = days_ago_to_iso(days_ago) if days_ago is not None else None

        enriched_jobs.append({
            "job_id": f"job_li_{job['job_id']}",
            "title": job["title"],
            "company": job["company"],
            "location": job["location"],
            "salary": None,
            "url": job["url"],
            "source": "linkedin",
            "level": categorize_level(job["title"]),
            "ai_focus": has_ai_focus(job["title"]),
            "posted": posted,
            "days_ago": days_ago,
        })

    # Apply filters (same as search_linkedin)
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

    return {
        "status": "ok",
        "jobs": filtered_jobs,
        "job_count": len(filtered_jobs),
        "total_scraped": len(enriched_jobs),
        "filtered_out": filtered_out,
    }
