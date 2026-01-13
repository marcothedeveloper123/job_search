"""Jobs.cz Search API with location support and filtering."""

import hashlib
import json
import re
import time
from pathlib import Path
from typing import Optional
from urllib.parse import urlencode

import requests
from bs4 import BeautifulSoup

from scripts.scrape_utils import parse_days_ago_cs, days_ago_to_iso, now_iso
from server.utils import categorize_level, has_ai_focus, level_rank

# Search results cache directory
SEARCH_CACHE_DIR = Path(__file__).parent.parent.parent / "data" / "runtime" / "searches"

# Location slugs for URL building
# Location codes for jobs.cz locality[code] param
LOCATION_CODES = {
    "praha": "R200000",
    "prague": "R200000",
    "brno": "R200001",
    "ostrava": "R200002",
    "plzen": "R200003",
    "liberec": "R200004",
    "olomouc": "R200005",
    "ceske-budejovice": "R200006",
    "hradec-kralove": "R200007",
    "pardubice": "R200008",
    "czech": "",  # Country-wide
    "czechia": "",
}

# User agent for requests
USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)


def _generate_search_id() -> str:
    """Generate unique search ID."""
    return f"search_cz_{hashlib.md5(now_iso().encode()).hexdigest()[:8]}"


def _parse_salary_czk(salary_text: str) -> Optional[str]:
    """Parse Czech salary format to normalized string."""
    if not salary_text:
        return None

    # Clean up the text
    text = salary_text.replace("\xa0", " ").replace(" ", " ").strip()

    # Match patterns like "55 000 – 85 000 Kč" or "od 50 000 Kč"
    match = re.search(r"(\d[\d\s]*)\s*[-–]\s*(\d[\d\s]*)\s*Kč", text)
    if match:
        min_sal = match.group(1).replace(" ", "")
        max_sal = match.group(2).replace(" ", "")
        return f"{int(min_sal):,} - {int(max_sal):,} CZK"

    match = re.search(r"od\s*(\d[\d\s]*)\s*Kč", text, re.I)
    if match:
        sal = match.group(1).replace(" ", "")
        return f"from {int(sal):,} CZK"

    match = re.search(r"(\d[\d\s]*)\s*Kč", text)
    if match:
        sal = match.group(1).replace(" ", "")
        return f"{int(sal):,} CZK"

    return None


def _extract_job_id(url: str) -> Optional[str]:
    """Extract numeric job ID from jobs.cz URL."""
    # Match /rpd/ID/ or /fp/ID/ patterns
    match = re.search(r"/(?:rpd|fp)/(\d+)", url)
    if match:
        return match.group(1)
    return None


# Remote work arrangement options
ARRANGEMENT_OPTIONS = {
    "remote": "work-mostly-from-home",      # Mostly from home
    "hybrid": "partial-work-from-home",     # Partial/hybrid
    "flexible": "flexible-hours",           # Flexible hours
}


def _build_search_url(
    query: str,
    location: Optional[str] = None,
    page: int = 1,
    remote: Optional[str] = None,
) -> str:
    """Build jobs.cz search URL using query params."""
    params = {"q": query}

    # Location as locality[code]
    if location:
        loc_code = LOCATION_CODES.get(location.lower(), "")
        if loc_code:
            params["locality[code]"] = loc_code

    if page > 1:
        params["page"] = str(page)

    # Remote work filter
    if remote:
        arrangement = ARRANGEMENT_OPTIONS.get(remote.lower(), remote)
        params["arrangement"] = arrangement

    return f"https://www.jobs.cz/prace/?{urlencode(params)}"


def _scrape_page(session: requests.Session, url: str) -> tuple[list[dict], bool]:
    """
    Scrape a single page of jobs.cz results.

    Returns:
        (jobs_list, has_next_page)
    """
    response = session.get(url, timeout=30)
    response.raise_for_status()

    soup = BeautifulSoup(response.text, "html.parser")
    jobs = []

    # Find all job cards
    cards = soup.select(".SearchResultCard")

    for card in cards:
        # Get title link
        title_link = card.select_one(".SearchResultCard__titleLink")
        if not title_link:
            continue

        href = title_link.get("href", "")
        job_id = _extract_job_id(href)
        if not job_id:
            continue

        title = title_link.get_text(strip=True)
        if not title or len(title) < 3:
            continue

        # Get company and location from footer
        company = None
        location = None
        footer = card.select_one(".SearchResultCard__footer")
        if footer:
            footer_text = footer.get_text(strip=True)
            # Footer format: "Company NamePraha – District" (no separator)
            # Split on city names
            for city in ["Praha", "Brno", "Ostrava", "Plzeň", "Olomouc", "Remote", "Vzdáleně"]:
                if city in footer_text:
                    idx = footer_text.index(city)
                    company = footer_text[:idx].strip() if idx > 0 else None
                    location = footer_text[idx:].strip()
                    break
            if not location:
                company = footer_text

        # Get salary if present
        salary = None
        salary_el = card.select_one('[data-test-ad-salary]')
        if salary_el:
            salary = _parse_salary_czk(salary_el.get_text(strip=True))
        else:
            # Try finding Kč in text
            salary_text = card.find(string=re.compile(r"\d+.*Kč"))
            if salary_text:
                salary = _parse_salary_czk(str(salary_text))

        # Get posting date
        posted_text = None
        status = card.select_one(".SearchResultCard__status")
        if status:
            posted_text = status.get_text(strip=True)

        # Build full URL
        full_url = href if href.startswith("http") else f"https://www.jobs.cz{href}"
        full_url = re.sub(r"\?.*$", "", full_url)

        jobs.append({
            "job_id": job_id,
            "title": title,
            "company": company,
            "location": location,
            "salary": salary,
            "url": full_url,
            "posted_text": posted_text,
        })

    # Check for next page
    has_next = bool(soup.find("a", href=re.compile(r"page=\d+")))

    return jobs, has_next


def search_jobscz(
    query: str,
    location: Optional[str] = None,
    remote: Optional[str] = None,
    days: int = 30,
    max_pages: int = 3,
    exclude_locations: Optional[list[str]] = None,
    exclude_companies: Optional[list[str]] = None,
    min_level: Optional[str] = None,
    ai_only: bool = False,
) -> dict:
    """
    Search jobs.cz for job listings.

    Args:
        query: Search keywords (e.g., "product manager")
        location: City or region (praha, brno, czech, etc.)
        remote: Work arrangement filter: "remote", "hybrid", "flexible"
        days: Posted within N days (filtering done post-scrape)
        max_pages: Pages to scrape (default 3)
        exclude_locations: Filter out jobs with these strings in location
        exclude_companies: Filter out these companies
        min_level: Minimum level (senior, staff, principal, leadership)
        ai_only: Only return jobs where ai_focus=True

    Returns:
        {"status": "ok", "search_id": "...", "jobs": [...], ...}
    """
    SEARCH_CACHE_DIR.mkdir(parents=True, exist_ok=True)

    session = requests.Session()
    session.headers.update({
        "User-Agent": USER_AGENT,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "cs,en;q=0.9",
    })

    all_jobs = []
    seen_ids = set()
    pages_fetched = 0

    try:
        for page_num in range(1, max_pages + 1):
            url = _build_search_url(query, location, page_num, remote)

            page_jobs, has_next = _scrape_page(session, url)
            pages_fetched += 1

            for job in page_jobs:
                if job["job_id"] not in seen_ids:
                    seen_ids.add(job["job_id"])
                    all_jobs.append(job)

            if not has_next:
                break

            # Rate limit courtesy
            time.sleep(1)

    except requests.RequestException as e:
        return {"status": "error", "error": str(e), "code": "SCRAPE_FAILED"}
    except Exception as e:
        return {"status": "error", "error": str(e), "code": "SCRAPE_FAILED"}

    # Enrich with computed fields
    enriched_jobs = []
    for job in all_jobs:
        days_ago = parse_days_ago_cs(job.get("posted_text", ""))
        posted = days_ago_to_iso(days_ago) if days_ago is not None else None

        enriched_jobs.append({
            "job_id": f"job_cz_{job['job_id']}",
            "title": job["title"],
            "company": job["company"],
            "location": job["location"],
            "salary": job["salary"],
            "url": job["url"],
            "source": "jobs.cz",
            "level": categorize_level(job["title"]),
            "ai_focus": has_ai_focus(job["title"]),
            "posted": posted,
            "days_ago": days_ago,
        })

    # Apply filters
    filtered_out = 0
    filtered_jobs = []

    for job in enriched_jobs:
        # Days filter (if we have days_ago)
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

    # Generate search ID and cache results
    search_id = _generate_search_id()
    cache_data = {
        "search_id": search_id,
        "query": query,
        "location": location,
        "days": days,
        "max_pages": max_pages,
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
        "pages_fetched": pages_fetched,
        "pages_requested": max_pages,
        "filtered_out": filtered_out,
    }
