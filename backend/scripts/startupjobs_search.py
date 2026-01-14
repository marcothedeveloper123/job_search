"""StartupJobs.cz Search API.

Config-driven with fallback to hardcoded defaults.
Edit data/scrapers/startupjobs.json to update API URL without code changes.
"""

import hashlib
import json
from pathlib import Path
from typing import Optional
from urllib.parse import urlencode

import requests

from scripts.scrape_utils import parse_iso_date, now_iso
from scripts.scraper_config import load_config, get_config_value
from server.utils import categorize_level, has_ai_focus


# Search results cache directory
SEARCH_CACHE_DIR = Path(__file__).parent.parent.parent / "data" / "runtime" / "searches"

# Load config (None if missing or invalid - will use hardcoded defaults)
_config = load_config("startupjobs")

# Config-driven values with hardcoded fallbacks
API_URL = get_config_value(_config, "api_url", "https://core.startupjobs.cz/api/search/offers")
JOB_URL_TEMPLATE = get_config_value(
    _config, "url_pattern.job_url_template",
    "https://www.startupjobs.cz/nabidka/{id}/{slug}"
)

# Location presets with coordinates
LOCATION_PRESETS = {
    "praha": "Praha:50.08584:14.422954:20km",
    "prague": "Praha:50.08584:14.422954:20km",
    "brno": "Brno:49.193878:16.606107:20km",
    "ostrava": "Ostrava:49.835:18.2925:20km",
    "plzen": "Plzeň:49.7384:13.3736:20km",
    "czech": "",  # Country-wide
    "czechia": "",
}

# Work mode mapping
WORK_MODES = {
    "remote": "remote",
    "hybrid": "hybrid",
    "onsite": "onsite",
}

# Seniority mapping
SENIORITY_MAP = {
    "junior": "junior",
    "medior": "medior",
    "senior": "senior",
}

# Query aliases - map common terms to startupjobs.cz profession slugs
QUERY_ALIASES = {
    "pm": "product-manager",
    "product": "product-manager",
    "product manager": "product-manager",
    "program manager": "program-manager",
    "project manager": "project-manager",
    "data scientist": "data-scientist",
    "data analyst": "data-analyst",
    "ux": "ux-designer",
    "ui": "ui-designer",
    "frontend": "frontend-developer",
    "backend": "backend-developer",
    "fullstack": "fullstack-developer",
    "devops": "devops",
    "qa": "qa-engineer",
    "marketing": "marketing",
    "sales": "sales",
}

USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)


def _generate_search_id() -> str:
    """Generate unique search ID."""
    return f"search_sj_{hashlib.md5(now_iso().encode()).hexdigest()[:8]}"


def _parse_salary(salary_data: dict) -> Optional[str]:
    """Parse salary object to string."""
    if not salary_data:
        return None

    min_sal = salary_data.get("min")
    max_sal = salary_data.get("max")
    currency = salary_data.get("currency", "CZK")
    measure = salary_data.get("measure", "month")

    if min_sal and max_sal:
        return f"{int(min_sal):,} - {int(max_sal):,} {currency}/{measure}"
    elif min_sal:
        return f"from {int(min_sal):,} {currency}/{measure}"
    elif max_sal:
        return f"up to {int(max_sal):,} {currency}/{measure}"
    return None




def search_startupjobs(
    query: str,
    location: Optional[str] = None,
    remote: Optional[str] = None,
    seniority: Optional[str] = None,
    days: int = 30,
    limit: int = 50,
    exclude_locations: Optional[list[str]] = None,
    exclude_companies: Optional[list[str]] = None,
    min_level: Optional[str] = None,
    ai_only: bool = False,
) -> dict:
    """
    Search startupjobs.cz for job listings.

    Args:
        query: Search keywords (e.g., "product manager")
        location: City (praha, brno) or None for all
        remote: Work mode: "remote", "hybrid", "onsite"
        seniority: Level filter: "junior", "medior", "senior"
        days: Posted within N days
        limit: Max results
        exclude_locations: Filter out jobs with these strings
        exclude_companies: Filter out these companies
        min_level: Minimum level (senior, staff, etc.)
        ai_only: Only return jobs where ai_focus=True

    Returns:
        {"status": "ok", "search_id": "...", "jobs": [...], ...}
    """
    SEARCH_CACHE_DIR.mkdir(parents=True, exist_ok=True)

    # Build API URL - use core.startupjobs.cz search endpoint
    params = [("page", "1"), ("startupOnly", "false")]

    # Query becomes fields[] param (profession filter)
    if query:
        query_lower = query.lower().strip()
        # Check aliases first, then convert to slug format
        field_slug = QUERY_ALIASES.get(query_lower, query_lower.replace(" ", "-"))
        params.append(("fields[]", field_slug))

    # Location (city name)
    if location:
        loc_name = location.lower()
        # Map common names to Czech
        loc_map = {"prague": "praha", "pilsen": "plzen"}
        loc_name = loc_map.get(loc_name, loc_name).capitalize()
        params.append(("location[]", loc_name))

    # Work mode
    if remote:
        mode = WORK_MODES.get(remote.lower(), remote)
        params.append(("workingModel[]", mode))

    # Seniority
    if seniority:
        sen = SENIORITY_MAP.get(seniority.lower(), seniority)
        params.append(("seniority[]", sen))

    url = f"{API_URL}?{urlencode(params)}"

    session = requests.Session()
    session.headers.update({
        "User-Agent": USER_AGENT,
        "Accept": "application/json",
        "Accept-Language": "cs,en;q=0.9",
    })

    try:
        response = session.get(url, timeout=30)
        response.raise_for_status()
        data = response.json()
    except requests.RequestException as e:
        return {"status": "error", "error": str(e), "code": "API_FAILED"}
    except json.JSONDecodeError as e:
        return {"status": "error", "error": f"Invalid JSON: {e}", "code": "API_FAILED"}

    # JSON-LD format: data may be object with "member" array, or a list directly
    if isinstance(data, list):
        result_set = data
    else:
        result_set = data.get("member", [])

    # Transform to standard job format (JSON-LD structure)
    enriched_jobs = []
    for item in result_set:
        # Use displayId (numeric) for job_id
        display_id = item.get("displayId", item.get("id", ""))
        job_id = f"job_sj_{display_id}"

        # Title is nested: {"cs": "...", "en": "..."}
        title_obj = item.get("title", {})
        title = title_obj.get("cs") or title_obj.get("en") or str(title_obj) if isinstance(title_obj, dict) else str(title_obj)

        # Company is an object with name
        company_obj = item.get("company", {})
        company = company_obj.get("name", "") if isinstance(company_obj, dict) else str(company_obj)

        # Location from locations array (API uses plural)
        # Format: [{name: {cs: "Praha", en: "Prague"}, ...}]
        location_arr = item.get("locations", []) or item.get("location", [])
        if isinstance(location_arr, list):
            loc_names = []
            for loc in location_arr:
                if isinstance(loc, dict):
                    # New format: {cs: "Praha", en: "Prague"}
                    if "cs" in loc or "en" in loc:
                        loc_names.append(loc.get("cs") or loc.get("en") or "")
                    # Old format: {name: {cs: "Praha"}}
                    elif "name" in loc:
                        name_obj = loc.get("name", {})
                        if isinstance(name_obj, dict):
                            loc_names.append(name_obj.get("cs") or name_obj.get("en") or "")
                        else:
                            loc_names.append(str(name_obj) if name_obj else "")
                else:
                    loc_names.append(str(loc) if loc else "")
            location_str = ", ".join(filter(None, loc_names)) or None
        else:
            location_str = None

        # Remote flag from workingModel array
        working_models = item.get("workingModel", [])
        is_remote = "remote" in working_models
        if is_remote and location_str:
            location_str = f"{location_str} (Remote)"
        elif is_remote:
            location_str = "Remote"

        # Salary from salary object
        salary_obj = item.get("salary", {})
        salary = _parse_salary(salary_obj) if salary_obj else None

        # URL from config template - supports {id} and {slug} placeholders
        slug = item.get("slug", "")
        if display_id:
            full_url = JOB_URL_TEMPLATE.replace("{id}", str(display_id)).replace("{slug}", slug)
        else:
            full_url = None

        # Posted date from boostedAt
        posted = item.get("boostedAt")
        days_ago = parse_iso_date(posted)

        enriched_jobs.append({
            "job_id": job_id,
            "title": title,
            "company": company,
            "location": location_str,
            "salary": salary,
            "url": full_url,
            "source": "startupjobs.cz",
            "level": categorize_level(title),
            "ai_focus": has_ai_focus(title),
            "posted": posted,
            "days_ago": days_ago,
            "is_remote": is_remote,
            "seniorities": item.get("seniority", []),
        })

    # Apply filters (API handles query via fields[] param)
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
            from server.utils import level_rank
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

    # Limit to requested count
    filtered_jobs = filtered_jobs[:limit]

    # Generate search ID and cache results
    search_id = _generate_search_id()
    cache_data = {
        "search_id": search_id,
        "query": query,
        "location": location,
        "remote": remote,
        "seniority": seniority,
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
        "total_from_api": len(result_set),
        "filtered_out": filtered_out,
    }
