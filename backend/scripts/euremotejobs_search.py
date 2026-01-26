"""EU Remote Jobs Search API using Playwright.

Config-driven with fallback to hardcoded defaults.
Edit data/scrapers/euremotejobs.json to update selectors without code changes.
"""

import hashlib
import json
import re
from pathlib import Path
from typing import Optional

from playwright.sync_api import sync_playwright

from scripts.scrape_utils import parse_days_ago_en, days_ago_to_iso, now_iso
from scripts.scraper_config import (
    load_config, get_selector, get_config_value, build_extraction_js
)
from server.utils import categorize_level, has_ai_focus

# Search results cache directory
SEARCH_CACHE_DIR = Path(__file__).parent.parent.parent / "data" / "runtime" / "searches"

# Load config (None if missing or invalid - will use hardcoded defaults)
_config = load_config("euremotejobs")

# Config-driven selectors with hardcoded fallbacks
CARD_SELECTOR = get_selector(_config, "card", 'a[href*="/job/"]')
LOAD_MORE_SELECTOR = get_config_value(
    _config, "pagination.selector", 'a.load_more_jobs, button.load_more_jobs, [class*="load-more"]'
)

# Region slugs for URL parameter
REGION_SLUGS = {
    "emea": "remote-jobs-emea",
    "eu_remote": "remote-jobs-emea",
    "europe": "remote-jobs-europe",
    "italy": "remote-jobs-italy",
    "germany": "remote-jobs-germany",
    "france": "remote-jobs-france",
    "spain": "remote-jobs-spain",
    "netherlands": "remote-jobs-netherlands",
    "uk": "remote-jobs-uk",
}

# Category slugs
CATEGORY_SLUGS = {
    "product": "product",
    "engineering": "engineering",
    "design": "design",
    "marketing": "marketing",
    "sales": "sales",
    "operations": "operations",
}

# Level slugs
LEVEL_SLUGS = {
    "entry": "entry-level",
    "junior": "1-2-years",
    "mid": "3-4-years",
    "senior": "5-years",
}


def _generate_search_id() -> str:
    """Generate unique search ID."""
    return f"search_er_{hashlib.md5(now_iso().encode()).hexdigest()[:8]}"


def _extract_slug_from_url(url: str) -> Optional[str]:
    """Extract job slug from URL path."""
    # /job/staff-product-manager-studio/ -> staff-product-manager-studio
    match = re.search(r"/job/([^/]+)/?", url)
    return match.group(1) if match else None


def _parse_salary(text: str) -> Optional[str]:
    """Parse salary text to normalized format."""
    if not text:
        return None
    # £91,755-£110,106 or €100,000-€140,000 or $120,000-$150,000
    text = text.strip()
    if any(c in text for c in "£€$"):
        return text
    return None


def _build_search_url(
    query: str,
    region: Optional[str] = None,
    category: Optional[str] = None,
    level: Optional[str] = None,
    high_salary: bool = False,
) -> str:
    """Build euremotejobs.com search URL."""
    params = [f"search_keywords={query.replace(' ', '+')}"]

    if region:
        slug = REGION_SLUGS.get(region.lower(), region)
        params.append(f"search_region={slug}")

    params.append("search_type=full-time")

    if high_salary:
        params.append("high_salary=1")

    if level:
        slug = LEVEL_SLUGS.get(level.lower(), "5-years")
        params.append(f"search_level={slug}")

    if category:
        slug = CATEGORY_SLUGS.get(category.lower(), category)
        params.append(f"search_category={slug}")

    return f"https://euremotejobs.com/?{'&'.join(params)}"


# JS: Extract job listings from euremotejobs.com search page.
# Finds all /job/{slug} links, parses title/company/location from link text,
# extracts "Posted X days ago" pattern and salary (£/€/$) from text content.
EXTRACT_JOBS_JS = """
() => {
    const jobs = [];
    const links = document.querySelectorAll('a[href*="/job/"]');
    const seen = new Set();

    links.forEach(link => {
        const href = link.getAttribute('href');
        if (!href) return;

        // Extract job slug from URL
        const slugMatch = href.match(/\\/job\\/([^/]+)/);
        if (!slugMatch) return;
        const slug = slugMatch[1];

        // Dedupe by slug
        if (seen.has(slug)) return;
        seen.add(slug);

        // Parse the link text content (title, company, location, tags, posted)
        const text = link.innerText.trim();
        const lines = text.split('\\n').map(l => l.trim()).filter(l => l);

        // First line is title
        const title = lines[0] || '';

        // Second line is usually company
        const company = lines[1] || '';

        // Third line is location
        const location = lines[2] || '';

        // Look for posted date pattern in lines
        let postedText = null;
        for (const line of lines) {
            const agoMatch = line.match(/Posted\\s+(\\d+\\s*(?:hour|day|week|month)s?\\s*ago)/i);
            if (agoMatch) {
                postedText = agoMatch[1];
                break;
            }
        }

        // Look for salary pattern
        let salary = null;
        const salaryMatch = text.match(/[£€$][\\d,]+(?:\\s*[-–]\\s*[£€$]?[\\d,]+)?/);
        if (salaryMatch) salary = salaryMatch[0];

        jobs.push({
            slug: slug,
            title: title,
            company: company,
            location: location,
            salary: salary,
            postedText: postedText,
            url: href.startsWith('http') ? href : 'https://euremotejobs.com' + href
        });
    });

    return jobs;
}
"""

# Use config-driven extraction JS if available, otherwise hardcoded default
_EXTRACT_JOBS_JS = build_extraction_js(_config, EXTRACT_JOBS_JS)


def search_euremotejobs(
    query: str,
    location: Optional[str] = None,
    category: Optional[str] = None,
    level: Optional[str] = None,
    high_salary: bool = False,
    days: int = 30,
    max_loads: int = 3,
    exclude_locations: Optional[list[str]] = None,
    exclude_companies: Optional[list[str]] = None,
    min_level: Optional[str] = None,
    ai_only: bool = False,
) -> dict:
    """
    Search euremotejobs.com for job listings.

    Args:
        query: Search keywords (e.g., "staff product manager")
        location: Region filter (emea, europe, italy, germany, etc.)
        category: Job category (product, engineering, design, etc.)
        level: Experience level (entry, junior, mid, senior)
        high_salary: Filter for high-salary listings
        days: Posted within N days
        max_loads: Max "Load More" clicks (each loads ~20 jobs)
        exclude_locations: Filter out jobs with these strings in location
        exclude_companies: Filter out these companies
        min_level: Minimum level (senior, staff, principal, leadership)
        ai_only: Only return jobs where ai_focus=True

    Returns:
        {"status": "ok", "search_id": "...", "jobs": [...], ...}
    """
    SEARCH_CACHE_DIR.mkdir(parents=True, exist_ok=True)

    url = _build_search_url(query, location, category, level, high_salary)
    all_jobs = []
    seen_slugs = set()

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()

            try:
                page.goto(url, timeout=60000)
                page.wait_for_timeout(5000)

                for load_num in range(max_loads):
                    # Extract current jobs
                    jobs = page.evaluate(_EXTRACT_JOBS_JS)

                    for job in jobs:
                        slug = job.get("slug")
                        if slug and slug not in seen_slugs:
                            seen_slugs.add(slug)
                            all_jobs.append(job)

                    # Try to load more
                    load_more = page.query_selector(LOAD_MORE_SELECTOR)
                    if load_more and load_more.is_visible():
                        load_more.click()
                        page.wait_for_timeout(2000)
                    else:
                        break

            finally:
                browser.close()

    except Exception as e:
        return {"status": "error", "error": str(e), "code": "SCRAPE_FAILED"}

    # Enrich with computed fields
    enriched_jobs = []
    for job in all_jobs:
        days_ago = parse_days_ago_en(job.get("postedText", ""))
        posted = days_ago_to_iso(days_ago) if days_ago is not None else None
        title = job.get("title", "")

        enriched_jobs.append({
            "job_id": f"job_er_{job['slug']}",
            "title": title,
            "company": job.get("company"),
            "location": job.get("location"),
            "salary": job.get("salary"),
            "url": job.get("url"),
            "source": "euremotejobs",
            "level": categorize_level(title),
            "ai_focus": has_ai_focus(title),
            "posted": posted,
            "days_ago": days_ago,
        })

    # Apply filters
    from server.utils import level_rank
    filtered_out = 0
    filtered_jobs = []

    for job in enriched_jobs:
        # Days filter
        if days and job.get("days_ago") is not None:
            if job["days_ago"] > days:
                filtered_out += 1
                continue

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

    # Generate search ID and cache
    search_id = _generate_search_id()
    cache_data = {
        "search_id": search_id,
        "query": query,
        "location": location,
        "days": days,
        "filters": {
            "exclude_locations": exclude_locations,
            "exclude_companies": exclude_companies,
            "min_level": min_level,
            "ai_only": ai_only,
        },
        "jobs": filtered_jobs,
        "all_jobs": enriched_jobs,
        "created_at": now_iso(),
    }

    cache_file = SEARCH_CACHE_DIR / f"{search_id}.json"
    cache_file.write_text(json.dumps(cache_data, indent=2))

    return {
        "status": "ok",
        "search_id": search_id,
        "jobs": filtered_jobs,
        "job_count": len(filtered_jobs),
        "filtered_out": filtered_out,
    }
