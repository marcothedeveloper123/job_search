"""
Job Search UI Server API Client.

These functions call the Job Search UI server API for the interactive workflow.
Server must be running at localhost:8000 for these to work.

Usage:
    from job_search import ingest_jobs, get_selections, post_deep_dive_simple

    # Push jobs to UI
    ingest_jobs(jobs=[{"job_id": "job_123", "title": "PM", "company": "Acme", "url": "..."}])

    # Get user selections
    selected = get_selections()

    # Post deep dive research
    post_deep_dive_simple(job_id="job_123", fit_score=8, verdict="Pursue")
"""

from __future__ import annotations

import json
import subprocess
import time
from pathlib import Path
from typing import Literal, Optional

from job_search import http


def _ensure_server() -> str | None:
    """Start server if not running. Returns error message or None on success."""
    import requests

    # Check if server is already running
    try:
        requests.get("http://localhost:8000/api/status", timeout=2)
        return None  # Already running
    except requests.RequestException:
        pass  # Not running, start it

    # Find project root (where pyproject.toml is)
    project_root = Path(__file__).parent.parent.parent
    if not (project_root / "pyproject.toml").exists():
        return "Cannot find project root"

    # Start server in background
    log_file = Path("/tmp/job-search-server.log")
    with open(log_file, "w") as f:
        subprocess.Popen(
            ["poetry", "run", "python", "-m", "server.app"],
            cwd=project_root,
            stdout=f,
            stderr=subprocess.STDOUT,
            start_new_session=True,
        )

    # Wait for server to come up
    for _ in range(10):
        time.sleep(0.5)
        try:
            requests.get("http://localhost:8000/api/status", timeout=2)
            return None  # Started successfully
        except requests.RequestException:
            continue

    return "Server failed to start (check /tmp/job-search-server.log)"


# --- Terse Output Formatters ---


def _sanitize(s: str) -> str:
    """Replace pipe delimiters in source data."""
    return (s or "").replace("|", "-")


def _short_id(job_id: str) -> str:
    """Shorten job_id: job_li_123 -> li_123, job_er_slug -> er_slug, etc."""
    if job_id.startswith("job_li_"):
        return "li_" + job_id[7:]
    elif job_id.startswith("job_er_"):
        return "er_" + job_id[7:]
    elif job_id.startswith("job_cz_"):
        return "cz_" + job_id[7:]
    elif job_id.startswith("job_sj_"):
        return "sj_" + job_id[7:]
    return job_id


def _normalize_id(job_id: str) -> str:
    """Expand short IDs back to full: li_123 -> job_li_123, etc."""
    if job_id.startswith("job_"):
        return job_id
    # Check for prefix_id pattern (e.g., li_123, in_abc, er_xyz)
    if "_" in job_id:
        parts = job_id.split("_", 1)
        if len(parts) == 2 and len(parts[0]) >= 2 and parts[1]:
            return "job_" + job_id
    # Assume bare numeric is LinkedIn
    if job_id.isdigit():
        return f"job_li_{job_id}"
    return job_id


def _fmt_job(j: dict) -> str:
    """Format job as pipe-delimited string for terse output."""
    jid = _short_id(j.get("job_id", ""))
    # X prefix for dead jobs
    if j.get("dead"):
        jid = "X" + jid

    level = j.get("level") or "-"
    level_short = {"senior": "sr", "staff": "st", "principal": "pr", "lead": "ld"}.get(level, "-")

    return "|".join([
        jid,
        _sanitize(j.get("title", "")),
        _sanitize(j.get("company", "")),
        _sanitize(j.get("loc") or j.get("location", "")),
        level_short,
        "ai" if j.get("ai") or j.get("ai_focus") else "-",
        "jd" if j.get("has_jd") or j.get("jd_text") else "-",
        (j.get("verdict") or "-").lower()[:5],
    ])


def _fmt_deep_dive(d: dict) -> str:
    """Format deep dive as pipe-delimited string for terse output."""
    jid = _short_id(d.get("job_id", ""))
    conclusions = d.get("conclusions") or {}
    recommendations = d.get("recommendations") or {}

    return "|".join([
        jid,
        _sanitize(d.get("company") or ""),
        _sanitize(d.get("title") or ""),
        d.get("status") or "-",
        (recommendations.get("verdict") or d.get("verdict") or "-").lower()[:5],
        str(conclusions.get("fit_score") or d.get("fit") or "-"),
    ])


def _fmt_application(a: dict) -> str:
    """Format application as pipe-delimited string for terse output."""
    app_id = a.get("application_id", "")
    if app_id.startswith("app_"):
        app_id = app_id[4:]

    job = a.get("job") or {}
    return "|".join([
        app_id,
        _sanitize(job.get("company") or a.get("company") or ""),
        _sanitize(job.get("title") or a.get("job_title") or ""),
        a.get("status") or "-",
        "cv" if a.get("has_cv") or a.get("cv_tailored") else "-",
        "cl" if a.get("has_cover") or a.get("cover_letter") else "-",
    ])


# --- Status & Auth ---


def status(full: bool = False) -> str | dict:
    """Combined health check: server running + LinkedIn auth.

    Auto-starts server if not running.
    Returns (terse): "OK | auth: yes | user: {name}" or "ERROR: ..."
    """
    # Auto-start server if needed
    err = _ensure_server()
    if err:
        return {"status": "error", "error": err} if full else f"ERROR: {err}"

    result = http.get("/api/status", timeout=30, error_code="SERVER_ERROR")
    if full:
        return result
    if result.get("status") == "error":
        return f"ERROR: {result.get('error', 'Unknown')}"
    auth = "yes" if result.get("linkedin_auth") else "no"
    user = result.get("linkedin_user", "-")
    # Surface auth check errors (selector broken, etc.)
    if result.get("auth_error"):
        return f"OK | auth: ERROR | {result.get('auth_code')}: {result.get('auth_error')}"
    return f"OK | auth: {auth} | user: {user}"


def auth_status() -> dict:
    """Check LinkedIn authentication status."""
    return http.get("/api/auth/status", timeout=30, error_code="AUTH_FAILED")


def login(full: bool = False) -> str | dict:
    """Open browser for LinkedIn login. Blocks until complete or timeout."""
    result = http.post("/api/auth/login", timeout=180, error_code="AUTH_FAILED")
    if full:
        return result
    if result.get("status") == "error":
        return f"ERROR: {result.get('error', 'Login failed')}"
    return "Login complete"


def help(command: Optional[str] = None) -> str:
    """Return terse output format documentation.

    Args:
        command: Specific function name, or None for all formats.
    """
    formats = {
        "get_jobs": "Format: {id}|{title}|{company}|{location}|{level}|{ai}|{jd}|{verdict}\n"
                    "  id: li_123 (LinkedIn), cz_456 (jobs.cz), sj_789 (startupjobs). X prefix = dead.\n"
                    "  level: sr (senior), st (staff), pr (principal), ld (lead), - (other)\n"
                    "  ai: 'ai' or '-'\n"
                    "  jd: 'jd' or '-'\n"
                    "  verdict: pursue, maybe, skip, or -",
        "get_deep_dives": "Format: {id}|{company}|{title}|{status}|{verdict}|{fit}",
        "get_applications": "Format: {id}|{company}|{title}|{status}|{cv}|{cl}\n"
                           "  cv: 'cv' if has tailored CV, '-' otherwise\n"
                           "  cl: 'cl' if has cover letter, '-' otherwise",
        "search_jobs": "Returns: 'Added N, filtered M, dupes K (T found)'",
        "get_selections": "Returns: 'claude: id1,id2 | user: id3'",
    }
    if command:
        return formats.get(command, f"No format doc for '{command}'")
    return "\n\n".join(f"**{k}**\n{v}" for k, v in formats.items())


# --- Filters ---

FILTERS_FILE = Path(__file__).parent.parent.parent / "data" / "profile" / "search-filters.json"


def get_filters() -> str:
    """Show current search filters."""
    if not FILTERS_FILE.exists():
        return "(no filters set)"
    try:
        filters = json.loads(FILTERS_FILE.read_text())
    except (json.JSONDecodeError, IOError):
        return "(no filters set)"
    if not filters:
        return "(no filters set)"
    lines = []
    for key, value in filters.items():
        if isinstance(value, list):
            lines.append(f"{key}: {', '.join(value)}")
        else:
            lines.append(f"{key}: {value}")
    return "\n".join(lines)


def set_filter(key: str, value: str) -> str:
    """Set a filter param. Comma-separated values become arrays."""
    filters = {}
    if FILTERS_FILE.exists():
        try:
            filters = json.loads(FILTERS_FILE.read_text())
        except (json.JSONDecodeError, IOError):
            pass
    # Parse comma-separated into array
    values = [v.strip() for v in value.split(",") if v.strip()]
    filters[key] = values
    FILTERS_FILE.parent.mkdir(parents=True, exist_ok=True)
    FILTERS_FILE.write_text(json.dumps(filters, indent=2))
    return "OK"


def clear_filter(key: str) -> str:
    """Remove a filter param."""
    if not FILTERS_FILE.exists():
        return "OK"
    try:
        filters = json.loads(FILTERS_FILE.read_text())
    except (json.JSONDecodeError, IOError):
        return "OK"
    if key in filters:
        del filters[key]
        FILTERS_FILE.write_text(json.dumps(filters, indent=2))
    return "OK"


def reset_filters() -> str:
    """Clear all filters."""
    if FILTERS_FILE.exists():
        FILTERS_FILE.write_text("{}")
    return "OK"


# --- Search ---


def search_jobs(
    query: str,
    location: Optional[str] = None,
    sources: Optional[list[str]] = None,
    days: int = 30,
    skip_filters: bool = False,
    full: bool = False,
) -> str | dict:
    """Search, filter, and ingest jobs in one call.

    Filters are loaded from user's search-filters.json (title, level, location, company).
    Results are auto-ingested to the board.

    Args:
        query: Job title/keywords to search for.
        location: Region/city (e.g., "Prague", "eu_remote").
        sources: Job boards to search. Default: all (["linkedin", "jobscz", "startupjobs"])
        days: Only jobs posted within N days. Default: 30
        skip_filters: Bypass search-filters.json for edge cases. Default: False
        full: If True, return full JSON. Default False returns terse summary.

    Returns (terse): "Added N, filtered M, dupes K (T found)"
    """
    payload = {
        "query": query,
        "location": location,
        "days": days,
        "skip_filters": skip_filters,
    }
    if sources is not None:
        payload["sources"] = sources
    result = http.post(
        "/api/search",
        timeout=300,
        error_code="SCRAPE_FAILED",
        json=payload,
    )
    if full:
        return result
    if result.get("status") == "error":
        return f"ERROR: {result.get('error', 'Unknown error')}"
    return f"Added {result.get('added', 0)}, filtered {result.get('filtered', 0)}, dupes {result.get('duplicates', 0)} ({result.get('total_found', 0)} found)"


def search_linkedin(
    query: str,
    region: Optional[str] = None,
    remote: Optional[bool] = None,
    days: int = 30,
    max_pages: int = 3,
    exclude_locations: Optional[list[str]] = None,
    exclude_companies: Optional[list[str]] = None,
    min_level: Optional[str] = None,
    ai_only: bool = False,
    exclude_existing: bool = True,
) -> dict:
    """DEPRECATED: Use search_jobs(sources=["linkedin"]) instead."""
    return http.post(
        "/api/search/linkedin",
        timeout=300,
        error_code="SCRAPE_FAILED",
        json={
            "query": query,
            "region": region,
            "remote": remote,
            "days": days,
            "max_pages": max_pages,
            "exclude_locations": exclude_locations,
            "exclude_companies": exclude_companies,
            "min_level": min_level,
            "ai_only": ai_only,
            "exclude_existing": exclude_existing,
        },
    )


def scrape_top_picks(
    exclude_locations: Optional[list[str]] = None,
    exclude_companies: Optional[list[str]] = None,
    min_level: Optional[str] = None,
    ai_only: bool = False,
    exclude_existing: bool = True,
) -> dict:
    """Scrape LinkedIn's personalized 'Top job picks for you'.

    This supplements search_linkedin() by letting LinkedIn's algorithm
    surface jobs based on your profile, rather than explicit queries.
    """
    return http.post(
        "/api/linkedin/top-picks",
        timeout=120,
        error_code="SCRAPE_FAILED",
        json={
            "exclude_locations": exclude_locations,
            "exclude_companies": exclude_companies,
            "min_level": min_level,
            "ai_only": ai_only,
            "exclude_existing": exclude_existing,
        },
    )


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
    exclude_existing: bool = True,
) -> dict:
    """DEPRECATED: Use search_jobs(sources=["jobscz"]) instead."""
    return http.post(
        "/api/search/jobscz",
        timeout=300,
        error_code="SCRAPE_FAILED",
        json={
            "query": query,
            "location": location,
            "remote": remote,
            "days": days,
            "max_pages": max_pages,
            "exclude_locations": exclude_locations,
            "exclude_companies": exclude_companies,
            "min_level": min_level,
            "ai_only": ai_only,
            "exclude_existing": exclude_existing,
        },
    )


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
    exclude_existing: bool = True,
) -> dict:
    """DEPRECATED: Use search_jobs(sources=["startupjobs"]) instead."""
    return http.post(
        "/api/search/startupjobs",
        timeout=300,
        error_code="SCRAPE_FAILED",
        json={
            "query": query,
            "location": location,
            "remote": remote,
            "seniority": seniority,
            "days": days,
            "limit": limit,
            "exclude_locations": exclude_locations,
            "exclude_companies": exclude_companies,
            "min_level": min_level,
            "ai_only": ai_only,
            "exclude_existing": exclude_existing,
        },
    )


def search_generic_board(
    name: str,
    query: str,
    location: Optional[str] = None,
    max_pages: int = 3,
    exclude_locations: Optional[list[str]] = None,
    exclude_companies: Optional[list[str]] = None,
    min_level: Optional[str] = None,
    ai_only: bool = False,
) -> dict:
    """Search a job board using config-driven generic scraper.

    Use this for custom job boards configured via `jbs scraper create`.

    Args:
        name: Scraper name (e.g., "indeed_nl")
        query: Search keywords
        location: Location filter (optional)
        max_pages: Pages to scrape (default: 3)
        exclude_locations: Filter out jobs in these locations
        exclude_companies: Filter out these companies
        min_level: Minimum level (senior, staff, etc.)
        ai_only: Only AI-focused jobs

    Returns:
        {"status": "ok", "jobs": [...], ...}
    """
    from scripts.generic_search import search_generic
    return search_generic(
        name=name,
        query=query,
        location=location,
        max_pages=max_pages,
        exclude_locations=exclude_locations,
        exclude_companies=exclude_companies,
        min_level=min_level,
        ai_only=ai_only,
    )


def get_search_results(search_id: str) -> dict:
    """Retrieve cached search results by search_id."""
    return http.get(f"/api/search/{search_id}", error_code="JOB_NOT_FOUND")


# --- JD Scraping ---


def _get_scraper_by_prefix(prefix: str) -> str | None:
    """Look up scraper name by job ID prefix."""
    from pathlib import Path
    import json
    scrapers_dir = Path(__file__).parent.parent.parent / "data" / "scrapers"
    if not scrapers_dir.exists():
        return None
    for cfg_file in scrapers_dir.glob("*.json"):
        try:
            config = json.loads(cfg_file.read_text())
            cfg_prefix = config.get("id_prefix", "").rstrip("_")
            if cfg_prefix == prefix:
                return cfg_file.stem
        except (json.JSONDecodeError, IOError):
            pass
    return None


def _get_jd_endpoint(job_id: str) -> tuple[str, str | None]:
    """Get JD endpoint and optional scraper name for job_id.

    Returns (endpoint, scraper_name) where scraper_name is set for generic scrapers.
    """
    # Builtin endpoints
    if job_id.startswith("job_er_"):
        return "/api/jd-er", None
    elif job_id.startswith("job_cz_"):
        return "/api/jd-cz", None
    elif job_id.startswith("job_sj_"):
        return "/api/jd-sj", None
    elif job_id.startswith("job_li_") or not job_id.startswith("job_"):
        return "/api/jd", None

    # Extract prefix and look up scraper
    parts = job_id[4:].split("_", 1)
    if len(parts) > 1:
        prefix = parts[0]
        scraper_name = _get_scraper_by_prefix(prefix)
        if scraper_name:
            return f"/api/jd-generic/{scraper_name}", scraper_name

    return "/api/jd", None  # Fallback to LinkedIn


def scrape_jd(job_id: str, full: bool = False) -> str | dict:
    """Scrape job description. Routes to correct source by job_id prefix."""
    job_id = _normalize_id(job_id)
    endpoint, _ = _get_jd_endpoint(job_id)
    result = http.get(f"{endpoint}/{job_id}", timeout=60, error_code="SCRAPE_FAILED")
    if full:
        return result
    if result.get("status") == "error":
        return f"ERROR: {result.get('error', 'Scrape failed')}"
    return "Scraped 1 JD"


def scrape_jds(job_ids: list[str], full: bool = False) -> str | dict:
    """Batch scrape job descriptions. Routes to correct source by job_id prefix."""
    if not job_ids:
        return "Scraped 0 JDs" if not full else {"scraped": 0}
    # Normalize IDs (accept both short and full formats)
    job_ids = [_normalize_id(jid) for jid in job_ids]

    # Builtin endpoints (have dedicated Python scrapers)
    builtin_endpoints = {
        "li": "/api/jd/batch",
        "er": "/api/jd-er/batch",
        "cz": "/api/jd-cz/batch",
        "sj": "/api/jd-sj/batch",
    }

    # Group by source prefix
    by_source: dict[str, list[str]] = {}
    for jid in job_ids:
        # Extract prefix (e.g., "in" from "job_in_abc123")
        if jid.startswith("job_"):
            parts = jid[4:].split("_", 1)
            prefix = parts[0] if len(parts) > 1 else "li"
        else:
            prefix = "li"
        by_source.setdefault(prefix, []).append(jid)

    # Scrape each source
    total_scraped = 0
    all_results = []
    for prefix, ids in by_source.items():
        if not ids:
            continue
        if prefix in builtin_endpoints:
            # Use builtin scraper
            result = http.post(builtin_endpoints[prefix], timeout=300, error_code="SCRAPE_FAILED", json={"job_ids": ids})
        else:
            # Look up config and use generic scraper
            scraper_name = _get_scraper_by_prefix(prefix)
            if scraper_name:
                result = http.post(f"/api/jd-generic/{scraper_name}/batch", timeout=300, error_code="SCRAPE_FAILED", json={"job_ids": ids})
            else:
                # Unknown prefix, skip
                continue
        total_scraped += result.get("scraped", result.get("succeeded", 0))
        if full:
            all_results.extend(result.get("results", []))
    if full:
        return {"scraped": total_scraped, "results": all_results}
    return f"Scraped {total_scraped} JDs"


def scrape_jd_cz(job_id: str, full: bool = False) -> str | dict:
    """Scrape job description from jobs.cz."""
    result = http.get(f"/api/jd-cz/{job_id}", timeout=60, error_code="SCRAPE_FAILED")
    if full:
        return result
    if result.get("status") == "error":
        return f"ERROR: {result.get('error', 'Scrape failed')}"
    return "Scraped 1 JD"


def scrape_jds_cz(job_ids: list[str], full: bool = False) -> str | dict:
    """Batch scrape job descriptions from jobs.cz."""
    result = http.post("/api/jd-cz/batch", timeout=300, error_code="SCRAPE_FAILED", json={"job_ids": job_ids})
    if full:
        return result
    if result.get("status") == "error":
        return f"ERROR: {result.get('error', 'Scrape failed')}"
    return f"Scraped {result.get('scraped', len(job_ids))} JDs"


def scrape_jd_sj(job_id: str, full: bool = False) -> str | dict:
    """Scrape job description from startupjobs.cz."""
    result = http.get(f"/api/jd-sj/{job_id}", timeout=60, error_code="SCRAPE_FAILED")
    if full:
        return result
    if result.get("status") == "error":
        return f"ERROR: {result.get('error', 'Scrape failed')}"
    return "Scraped 1 JD"


def scrape_jds_sj(job_ids: list[str], full: bool = False) -> str | dict:
    """Batch scrape job descriptions from startupjobs.cz."""
    result = http.post("/api/jd-sj/batch", timeout=300, error_code="SCRAPE_FAILED", json={"job_ids": job_ids})
    if full:
        return result
    if result.get("status") == "error":
        return f"ERROR: {result.get('error', 'Scrape failed')}"
    return f"Scraped {result.get('scraped', len(job_ids))} JDs"


def scrape_jd_er(job_id: str, full: bool = False) -> str | dict:
    """Scrape job description from euremotejobs.com."""
    result = http.get(f"/api/jd-er/{job_id}", timeout=60, error_code="SCRAPE_FAILED")
    if full:
        return result
    if result.get("status") == "error":
        return f"ERROR: {result.get('error', 'Scrape failed')}"
    return "Scraped 1 JD"


def scrape_jds_er(job_ids: list[str], full: bool = False) -> str | dict:
    """Batch scrape job descriptions from euremotejobs.com."""
    result = http.post("/api/jd-er/batch", timeout=300, error_code="SCRAPE_FAILED", json={"job_ids": job_ids})
    if full:
        return result
    if result.get("status") == "error":
        return f"ERROR: {result.get('error', 'Scrape failed')}"
    return f"Scraped {result.get('scraped', len(job_ids))} JDs"


# --- Priority, Stage, Verdict ---


def set_priority(job_id: str, priority: Optional[str], full: bool = False) -> str | dict:
    """Set priority for a job: 'high', 'medium', 'low', or None to clear."""
    job_id = _normalize_id(job_id)
    result = http.post("/api/jobs/priority", error_code="JOB_NOT_FOUND", json={"job_id": job_id, "priority": priority})
    if full:
        return result
    if result.get("status") == "error":
        return f"ERROR: {result.get('error', 'Failed')}"
    return f"Set priority: {priority or 'cleared'}"


def move_to_stage(job_id: str, stage: str, full: bool = False) -> str | dict:
    """Move job to a workflow stage: 'select', 'deep_dive', 'application'."""
    job_id = _normalize_id(job_id)
    result = http.post("/api/jobs/stage", error_code="JOB_NOT_FOUND", json={"job_id": job_id, "stage": stage})
    if full:
        return result
    if result.get("status") == "error":
        return f"ERROR: {result.get('error', 'Failed')}"
    return f"Set stage: {stage}"


def set_verdict(job_id: str, verdict: str, full: bool = False) -> str | dict:
    """Set verdict for a job: 'Pursue', 'Maybe', 'Skip'."""
    job_id = _normalize_id(job_id)
    result = http.post("/api/jobs/verdict", error_code="JOB_NOT_FOUND", json={"job_id": job_id, "verdict": verdict})
    if full:
        return result
    if result.get("status") == "error":
        return f"ERROR: {result.get('error', 'Failed')}"
    return f"Set verdict: {verdict}"


# --- Archive ---


def archive_jobs(job_ids: list[str], full: bool = False) -> str | dict:
    """Archive jobs (soft delete)."""
    job_ids = [_normalize_id(jid) for jid in job_ids]
    result = http.post("/api/jobs/archive", json={"job_ids": job_ids})
    if full:
        return result
    return f"Archived {result.get('updated', len(job_ids))}"


def unarchive_jobs(job_ids: list[str], full: bool = False) -> str | dict:
    """Unarchive jobs."""
    job_ids = [_normalize_id(jid) for jid in job_ids]
    result = http.post("/api/jobs/unarchive", json={"job_ids": job_ids})
    if full:
        return result
    return f"Unarchived {result.get('updated', len(job_ids))}"


def reorder_jobs(job_ids: list[str], full: bool = False) -> str | dict:
    """Set manual sort order for jobs. Jobs appear in the order given."""
    job_ids = [_normalize_id(jid) for jid in job_ids]
    result = http.post("/api/jobs/reorder", json={"job_ids": job_ids})
    if full:
        return result
    return f"Reordered {len(job_ids)} jobs"


def mark_dead(job_ids: list[str], full: bool = False) -> str | dict:
    """Mark listings as dead (removed, filled, broken link)."""
    job_ids = [_normalize_id(jid) for jid in job_ids]
    result = http.post("/api/jobs/dead", json={"job_ids": job_ids})
    if full:
        return result
    return f"Marked {result.get('updated', len(job_ids))} dead"


# --- Notes ---


def add_note(job_id: str, text: str, full: bool = False) -> str | dict:
    """Add a note for a job."""
    job_id = _normalize_id(job_id)
    result = http.post("/api/notes", error_code="JOB_NOT_FOUND", json={"job_id": job_id, "text": text})
    if full:
        return result
    if result.get("status") == "error":
        return f"ERROR: {result.get('error', 'Failed')}"
    return "Note added"


def remove_note(note_id: str, full: bool = False) -> str | dict:
    """Remove a note by ID."""
    result = http.delete(f"/api/notes/{note_id}", error_code="JOB_NOT_FOUND")
    if full:
        return result
    if result.get("status") == "error":
        return f"ERROR: {result.get('error', 'Failed')}"
    return "Note removed"


def get_notes(job_id: str, full: bool = False) -> str | dict:
    """Get notes for a job."""
    job_id = _normalize_id(job_id)
    result = http.get(f"/api/notes/{job_id}", error_code="JOB_NOT_FOUND")
    if full:
        return result
    notes = result.get("notes", [])
    if not notes:
        return "(no notes)"
    return "\n".join(f"{n.get('id', '-')}|{_sanitize(n.get('text', ''))}" for n in notes)


# --- Selections ---


def select_jobs(job_ids: list[str], source: str = "claude", full: bool = False) -> str | dict:
    """Select jobs with source attribution ('claude' or 'user')."""
    job_ids = [_normalize_id(jid) for jid in job_ids]
    result = http.post("/api/selections/select", json={"job_ids": job_ids, "source": source})
    if full:
        return result
    return f"Selected {len(job_ids)}"


def deselect_jobs(job_ids: list[str], full: bool = False) -> str | dict:
    """Deselect jobs."""
    job_ids = [_normalize_id(jid) for jid in job_ids]
    result = http.post("/api/selections/deselect", json={"job_ids": job_ids})
    if full:
        return result
    return f"Deselected {len(job_ids)}"


def get_selections(source: Optional[str] = None, full: bool = False) -> str | dict:
    """Get selections, optionally filtered by source."""
    params = {"source": source} if source else {}
    result = http.get("/api/selections", params=params)
    if "error" in result:
        if full:
            return {"claude": [], "user": []} if source is None else []
        return "(no selections)"
    if full:
        return result
    # Terse format: "claude: id1,id2 | user: id3"
    claude_ids = result.get("claude", [])
    user_ids = result.get("user", [])
    parts = []
    if claude_ids:
        parts.append(f"claude: {','.join(_short_id(i) for i in claude_ids)}")
    if user_ids:
        parts.append(f"user: {','.join(_short_id(i) for i in user_ids)}")
    return " | ".join(parts) if parts else "(no selections)"


def save_selections(ids: list[str]) -> dict:
    """DEPRECATED: Use select_jobs() and deselect_jobs() instead."""
    return http.post("/api/selections", json={"selected_ids": ids})


# --- Jobs ---


def get_jobs(
    ids: Optional[list[str]] = None,
    include_archived: bool = False,
    full: bool = False,
    limit: Optional[int] = None,
    page: int = 1,
) -> str | dict:
    """Get job list from the UI server.

    Args:
        full: If True, return full JSON response with jd_text and nested deep_dive.
              Default False returns terse pipe-delimited strings.
        limit: Max jobs per page (default: None = all for active, 20 for archived)
        page: Page number (1-indexed)

    Terse format: {id}|{title}|{company}|{location}|{level}|{ai}|{jd}|{verdict}
    """
    params = {"include_archived": str(include_archived).lower()}
    if not full:
        params["slim"] = "true"
    if ids:
        params["ids"] = ",".join(ids)
    result = http.get("/api/jobs", params=params)
    if not isinstance(result, dict) or "jobs" not in result:
        return "(no jobs)" if not full else {"jobs": []}
    if full:
        return result
    jobs = result.get("jobs", [])
    # Apply pagination
    if limit:
        total = len(jobs)
        total_pages = (total + limit - 1) // limit if total > 0 else 1
        start = (page - 1) * limit
        end = start + limit
        jobs = jobs[start:end]
        lines = [_fmt_job(j) for j in jobs]
        if total_pages > 1:
            lines.append(f"--page={page}/{total_pages}")
        return "\n".join(lines) or "(no jobs)"
    return "\n".join(_fmt_job(j) for j in jobs) or "(no jobs)"


def get_job(job_id: str) -> dict:
    """Get a single job by ID."""
    job_id = _normalize_id(job_id)
    return http.get(f"/api/jobs/{job_id}")


def ingest_jobs(
    jobs: list[dict],
    dedupe_by: Literal["job_id", "title_company", "none"] = "job_id",
) -> dict:
    """Push jobs with server-side deduplication."""
    result = http.post("/api/jobs/ingest", timeout=30, json={"jobs": jobs, "dedupe_by": dedupe_by})
    if "error" in result and "added" not in result:
        result["added"] = 0
        result["skipped"] = 0
    return result


def push_jobs(jobs: list[dict], search_params: Optional[dict] = None) -> dict:
    """DEPRECATED: Use ingest_jobs() for deduplication support."""
    result = http.post("/api/jobs", timeout=30, json={"jobs": jobs, "search_params": search_params})
    if "error" in result and "job_count" not in result:
        result["job_count"] = 0
    return result


def remove_jobs(ids: list[str], full: bool = False) -> str | dict:
    """Remove specific jobs from the UI by ID."""
    result = http.delete("/api/jobs", json={"ids": ids})
    if full:
        return result
    return f"Deleted {result.get('deleted', len(ids))}"


def update_job(
    job_id: str,
    title: Optional[str] = None,
    company: Optional[str] = None,
    location: Optional[str] = None,
    salary: Optional[str] = None,
    url: Optional[str] = None,
    source: Optional[str] = None,
    level: Optional[str] = None,
    ai_focus: Optional[bool] = None,
    posted: Optional[str] = None,
    days_ago: Optional[int] = None,
) -> dict:
    """Update specific fields of a job."""
    updates = {
        k: v for k, v in {
            "title": title, "company": company, "location": location, "salary": salary,
            "url": url, "source": source, "level": level, "ai_focus": ai_focus,
            "posted": posted, "days_ago": days_ago,
        }.items() if v is not None
    }
    if not updates:
        return {"status": "error", "error": "No fields to update"}
    return http.patch(f"/api/jobs/{job_id}", json=updates)


# --- Deep Dives ---


def get_deep_dives(
    include_archived: bool = False,
    full: bool = False,
    limit: Optional[int] = None,
    page: int = 1,
) -> str | dict:
    """Get all deep dives from the UI.

    Args:
        full: If True, return full JSON response with all research data.
              Default False returns terse pipe-delimited strings.
        limit: Max items per page
        page: Page number (1-indexed)

    Terse format: {id}|{company}|{title}|{status}|{verdict}|{fit}
    """
    params = {}
    if include_archived:
        params["include_archived"] = "true"
    if not full:
        params["slim"] = "true"
    result = http.get("/api/deep-dives", params=params)
    if not isinstance(result, dict) or "deep_dives" not in result:
        return "(no deep dives)" if not full else {"deep_dives": []}
    if full:
        return result
    dives = result.get("deep_dives", [])
    # Apply pagination
    if limit:
        total = len(dives)
        total_pages = (total + limit - 1) // limit if total > 0 else 1
        start = (page - 1) * limit
        end = start + limit
        dives = dives[start:end]
        lines = [_fmt_deep_dive(d) for d in dives]
        if total_pages > 1:
            lines.append(f"--page={page}/{total_pages}")
        return "\n".join(lines) or "(no deep dives)"
    return "\n".join(_fmt_deep_dive(d) for d in dives) or "(no deep dives)"


def get_deep_dive(job_id: str) -> Optional[dict]:
    """Get a single deep dive by job ID."""
    result = get_deep_dives()
    dives = result.get("deep_dives", [])
    return next((d for d in dives if d.get("job_id") == job_id), None)


def post_deep_dive(
    job_id: str,
    research: Optional[dict] = None,
    research_notes: Optional[dict] = None,
    insights: Optional[dict] = None,
    conclusions: Optional[dict] = None,
    recommendations: Optional[dict] = None,
) -> dict:
    """Post deep-dive research for a job to the UI."""
    job_id = _normalize_id(job_id)
    payload = {
        "job_id": job_id,
        "research": research or {},
        "insights": insights or {},
        "conclusions": conclusions or {},
        "recommendations": recommendations or {},
    }
    if research_notes is not None:
        payload["research_notes"] = research_notes
    return http.post("/api/deep-dives", timeout=30, json=payload)


def post_deep_dive_simple(
    job_id: str,
    # Company research
    company_size: Optional[str] = None,
    company_funding: Optional[str] = None,
    company_stage: Optional[str] = None,
    company_product: Optional[str] = None,
    company_market: Optional[str] = None,
    # Sentiment research (itemized with sentiment indicators)
    employee_sentiment: Optional[list[dict]] = None,
    customer_sentiment: Optional[list[dict]] = None,
    # Role research
    role_scope: Optional[str] = None,
    role_team: Optional[str] = None,
    role_tech_stack: Optional[str] = None,
    # Context research (itemized with sentiment indicators)
    market_context: Optional[list[dict]] = None,
    interview_process: Optional[list[dict]] = None,
    remote_reality: Optional[list[dict]] = None,
    # Analysis
    comparison: Optional[str] = None,
    posting_analysis: Optional[str] = None,
    fit_explanation: Optional[str] = None,
    # Conclusions
    fit_score: Optional[int] = None,
    concerns: Optional[list[str]] = None,
    attractions: Optional[list[str]] = None,
    verdict: Optional[str] = None,
    questions_to_ask: Optional[list[str]] = None,
    next_steps: Optional[list[str]] = None,
    research_notes: Optional[dict] = None,
) -> dict:
    """Post deep-dive research with flat arguments (Desktop Commander friendly).

    Sentiment and context fields use itemized format:
        employee_sentiment: [{"finding": "[Glassdoor 4.1/5](url)", "sentiment": "positive"}, ...]
        customer_sentiment: [{"finding": "[G2 4.6/5](url)", "sentiment": "positive"}, ...]
        market_context: [{"finding": "Competes with X, Y", "sentiment": "neutral"}, ...]
        interview_process: [{"finding": "4 rounds, tech heavy", "sentiment": "negative"}, ...]
        remote_reality: [{"finding": "Truly remote, async-first", "sentiment": "positive"}, ...]

    research_notes: Structured findings with sources and sentiment. Format:
        {
            "employee": [{"finding": "...", "sentiment": "positive|negative|neutral"}, ...],
            "customer": [...],
            "company": [...]
        }
    """
    return post_deep_dive(
        job_id=job_id,
        research={
            "company": {
                "size": company_size, "funding": company_funding, "stage": company_stage,
                "product": company_product, "market": company_market,
            },
            "sentiment": {
                "employee": employee_sentiment or [], "customer": customer_sentiment or [],
            },
            "role": {"scope": role_scope, "team": role_team, "tech_stack": role_tech_stack},
            "context": {
                "market": market_context or [], "interview_process": interview_process or [],
                "remote_reality": remote_reality or [],
            },
        },
        research_notes=research_notes,
        insights={"comparison": comparison, "posting_analysis": posting_analysis},
        conclusions={
            "fit_score": fit_score, "fit_explanation": fit_explanation,
            "concerns": concerns or [], "attractions": attractions or [],
        },
        recommendations={"verdict": verdict, "questions_to_ask": questions_to_ask or [], "next_steps": next_steps or []},
    )


def update_deep_dive(
    job_id: str,
    jd: Optional[dict] = None,
    enhanced_insights: Optional[dict] = None,
    research: Optional[dict] = None,
    research_notes: Optional[dict] = None,
    insights: Optional[dict] = None,
    conclusions: Optional[dict] = None,
    recommendations: Optional[dict] = None,
    status: Optional[str] = None,
    # Company research
    company_size: Optional[str] = None,
    company_funding: Optional[str] = None,
    company_stage: Optional[str] = None,
    company_product: Optional[str] = None,
    company_market: Optional[str] = None,
    # Sentiment research (itemized with sentiment indicators)
    employee_sentiment: Optional[list[dict]] = None,
    customer_sentiment: Optional[list[dict]] = None,
    # Role research
    role_scope: Optional[str] = None,
    role_team: Optional[str] = None,
    role_tech_stack: Optional[str] = None,
    # Context research (itemized with sentiment indicators)
    market_context: Optional[list[dict]] = None,
    interview_process: Optional[list[dict]] = None,
    remote_reality: Optional[list[dict]] = None,
    # Analysis
    comparison: Optional[str] = None,
    posting_analysis: Optional[str] = None,
    fit_explanation: Optional[str] = None,
    # Conclusions
    fit_score: Optional[int] = None,
    concerns: Optional[list[str]] = None,
    attractions: Optional[list[str]] = None,
    verdict: Optional[str] = None,
    questions_to_ask: Optional[list[str]] = None,
    next_steps: Optional[list[str]] = None,
) -> dict:
    """Update specific fields of an existing deep dive.

    Sentiment and context fields use itemized format:
        employee_sentiment: [{"finding": "...", "sentiment": "positive|negative|neutral"}, ...]
        customer_sentiment: [{"finding": "...", "sentiment": "..."}, ...]
        market_context: [{"finding": "...", "sentiment": "..."}, ...]
        interview_process: [{"finding": "...", "sentiment": "..."}, ...]
        remote_reality: [{"finding": "...", "sentiment": "..."}, ...]
    """
    job_id = _normalize_id(job_id)
    payload = {}
    if jd is not None:
        payload["jd"] = jd
    if enhanced_insights is not None:
        payload["enhanced_insights"] = enhanced_insights
    if research_notes is not None:
        payload["research_notes"] = research_notes
    if status is not None:
        payload["status"] = status

    # Build research from flat fields + passed dict
    research_update = research.copy() if research else {}
    company_fields = {k: v for k, v in {
        "size": company_size, "funding": company_funding, "stage": company_stage,
        "product": company_product, "market": company_market,
    }.items() if v is not None}
    if company_fields:
        research_update["company"] = {**research_update.get("company", {}), **company_fields}
    sentiment_fields = {k: v for k, v in {
        "employee": employee_sentiment, "customer": customer_sentiment,
    }.items() if v is not None}
    if sentiment_fields:
        research_update["sentiment"] = {**research_update.get("sentiment", {}), **sentiment_fields}
    role_fields = {k: v for k, v in {
        "scope": role_scope, "team": role_team, "tech_stack": role_tech_stack,
    }.items() if v is not None}
    if role_fields:
        research_update["role"] = {**research_update.get("role", {}), **role_fields}
    context_fields = {k: v for k, v in {
        "market": market_context, "interview_process": interview_process,
        "remote_reality": remote_reality,
    }.items() if v is not None}
    if context_fields:
        research_update["context"] = {**research_update.get("context", {}), **context_fields}
    if research_update:
        payload["research"] = research_update

    # Build insights
    insights_update = insights.copy() if insights else {}
    for key, val in {"comparison": comparison, "posting_analysis": posting_analysis}.items():
        if val is not None:
            insights_update[key] = val
    if insights_update:
        payload["insights"] = insights_update

    # Build conclusions
    conclusions_update = conclusions.copy() if conclusions else {}
    for key, val in {"fit_score": fit_score, "fit_explanation": fit_explanation}.items():
        if val is not None:
            conclusions_update[key] = val
    if concerns is not None:
        conclusions_update["concerns"] = concerns
    if attractions is not None:
        conclusions_update["attractions"] = attractions
    if conclusions_update:
        payload["conclusions"] = conclusions_update

    # Build recommendations
    recommendations_update = recommendations.copy() if recommendations else {}
    if verdict is not None:
        recommendations_update["verdict"] = verdict
    if questions_to_ask is not None:
        recommendations_update["questions_to_ask"] = questions_to_ask
    if next_steps is not None:
        recommendations_update["next_steps"] = next_steps
    if recommendations_update:
        payload["recommendations"] = recommendations_update

    return http.patch(f"/api/deep-dives/{job_id}", timeout=30, json=payload)


def delete_deep_dive(job_id: str, full: bool = False) -> str | dict:
    """Delete a deep dive by job ID."""
    job_id = _normalize_id(job_id)
    result = http.delete(f"/api/deep-dives/{job_id}")
    if full:
        return result
    return "Deleted 1 deep dive"


def delete_deep_dives(job_ids: list[str], full: bool = False) -> str | dict:
    """Delete multiple deep dives by job IDs."""
    job_ids = [_normalize_id(jid) for jid in job_ids]
    result = http.post("/api/deep-dives/delete", json={"job_ids": job_ids})
    if full:
        return result
    return f"Deleted {result.get('deleted', len(job_ids))} deep dives"


def archive_deep_dives(job_ids: list[str], full: bool = False) -> str | dict:
    """Archive deep dives (hide from default list view)."""
    job_ids = [_normalize_id(jid) for jid in job_ids]
    result = http.post("/api/deep-dives/archive", json={"job_ids": job_ids})
    if full:
        return result
    return f"Archived {result.get('updated', len(job_ids))} deep dives"


def unarchive_deep_dives(job_ids: list[str], full: bool = False) -> str | dict:
    """Unarchive deep dives."""
    job_ids = [_normalize_id(jid) for jid in job_ids]
    result = http.post("/api/deep-dives/unarchive", json={"job_ids": job_ids})
    if full:
        return result
    return f"Unarchived {result.get('updated', len(job_ids))} deep dives"


# --- Company Knowledge ---


def get_prior_company_research(company_name: str) -> dict:
    """
    Check if we have existing research for this company.
    Call before starting deep dive research to avoid duplication.

    Returns:
        found: bool - whether prior research exists
        company_name: str - normalized company name
        research_notes: dict - structured findings (employee/customer/company)
        research: dict - legacy company research (size, funding, stage, product, market)
        summary: str - condensed summary (saves tokens)
        source_job_ids: list - which deep dives this came from
        last_updated: str - when the best source was last updated
    """
    return http.get(f"/api/knowledge/company/{company_name}", timeout=30)


# --- Application Prep API (Step 3) ---


def prepare_application(job_id: str) -> dict:
    """Initiate application preparation for a job."""
    job_id = _normalize_id(job_id)
    return http.post("/api/applications/prepare", json={"job_id": job_id})


def get_applications(
    include_archived: bool = False,
    full: bool = False,
    limit: Optional[int] = None,
    page: int = 1,
) -> str | dict:
    """List all application preps.

    Args:
        full: If True, return full JSON response with CV/cover letter content.
              Default False returns terse pipe-delimited strings.
        limit: Max items per page
        page: Page number (1-indexed)

    Terse format: {id}|{company}|{title}|{status}|{cv}|{cl}
    """
    params = {}
    if include_archived:
        params["include_archived"] = "true"
    result = http.get("/api/applications", params=params)
    if not isinstance(result, dict) or "applications" not in result:
        return "(no applications)" if not full else {"applications": []}
    if full:
        return result
    apps = result.get("applications", [])
    # Apply pagination
    if limit:
        total = len(apps)
        total_pages = (total + limit - 1) // limit if total > 0 else 1
        start = (page - 1) * limit
        end = start + limit
        apps = apps[start:end]
        lines = [_fmt_application(a) for a in apps]
        if total_pages > 1:
            lines.append(f"--page={page}/{total_pages}")
        return "\n".join(lines) or "(no applications)"
    return "\n".join(_fmt_application(a) for a in apps) or "(no applications)"


def get_application(application_id: str) -> Optional[dict]:
    """Get full application prep data."""
    result = http.get(f"/api/applications/{application_id}")
    return None if result.get("status") == "error" else result


def delete_application(application_id: str, full: bool = False) -> str | dict:
    """Delete application prep and all files."""
    result = http.delete(f"/api/applications/{application_id}")
    if full:
        return result
    return "Deleted 1 application"


def archive_applications(application_ids: list[str], full: bool = False) -> str | dict:
    """Archive applications (hide from default list view)."""
    result = http.post("/api/applications/archive", json={"application_ids": application_ids})
    if full:
        return result
    return f"Archived {result.get('updated', len(application_ids))} applications"


def unarchive_applications(application_ids: list[str], full: bool = False) -> str | dict:
    """Unarchive applications."""
    result = http.post("/api/applications/unarchive", json={"application_ids": application_ids})
    if full:
        return result
    return f"Unarchived {result.get('updated', len(application_ids))} applications"


def update_application_jd(application_id: str, jd: str) -> dict:
    """Save scraped job description."""
    return http.put(f"/api/applications/{application_id}/jd", json={"jd": jd})


def update_application_gap_analysis(application_id: str, gap_analysis: dict) -> dict:
    """Save gap analysis."""
    return http.put(f"/api/applications/{application_id}/gap-analysis", json={"gap_analysis": gap_analysis})


def update_application_cv(application_id: str, cv_tailored: str) -> dict:
    """Save tailored CV. Versions previous if exists."""
    return http.put(f"/api/applications/{application_id}/cv", json={"cv_tailored": cv_tailored})


def update_application_cover(application_id: str, cover_letter: str) -> dict:
    """Save cover letter."""
    return http.put(f"/api/applications/{application_id}/cover", json={"cover_letter": cover_letter})


def update_application_interview_prep(application_id: str, interview_prep: dict) -> dict:
    """Save interview prep notes."""
    return http.put(f"/api/applications/{application_id}/interview-prep", json={"interview_prep": interview_prep})


def update_application_status(application_id: str, status: str, error: str | None = None) -> dict:
    """Update application status."""
    return http.put(f"/api/applications/{application_id}/status", json={"status": status, "error": error})


def update_application(
    application_id: str,
    cv_tailored: Optional[str] = None,
    cover_letter: Optional[str] = None,
    gap_analysis: Optional[dict] = None,
    interview_prep: Optional[dict] = None,
    salary_research: Optional[dict] = None,
    referral_search: Optional[dict] = None,
    follow_up: Optional[dict] = None,
    status: Optional[str] = None,
) -> dict:
    """Update multiple application fields at once.

    Args:
        application_id: The application ID
        cv_tailored: Tailored CV content (markdown)
        cover_letter: Cover letter content (markdown)
        gap_analysis: Gap analysis with matches, partial_matches, gaps, missing_stories
        interview_prep: Interview prep with what_to_say, what_not_to_say, questions_to_ask, red_flags
        salary_research: Salary intel with range, anchoring_strategy
        referral_search: Referral hunting results with contacts, channel_priority
        follow_up: Follow-up timeline with milestones, backup_contacts
        status: Application status
    """
    results = []
    if cv_tailored is not None:
        results.append(update_application_cv(application_id, cv_tailored))
    if cover_letter is not None:
        results.append(update_application_cover(application_id, cover_letter))
    if gap_analysis is not None:
        results.append(update_application_gap_analysis(application_id, gap_analysis))
    if interview_prep is not None:
        results.append(update_application_interview_prep(application_id, interview_prep))
    if salary_research is not None:
        results.append(http.put(f"/api/applications/{application_id}/salary-research", json={"salary_research": salary_research}))
    if referral_search is not None:
        results.append(http.put(f"/api/applications/{application_id}/referral-search", json={"referral_search": referral_search}))
    if follow_up is not None:
        results.append(http.put(f"/api/applications/{application_id}/follow-up", json={"follow_up": follow_up}))
    if status is not None:
        results.append(update_application_status(application_id, status))
    if not results:
        return {"status": "ok", "message": "No fields to update"}
    # Return last result or aggregate errors
    errors = [r for r in results if r.get("status") == "error"]
    if errors:
        return {"status": "error", "errors": errors}
    return {"status": "ok", "updated": len(results)}


# --- Pipeline Overview ---


def pipeline(full: bool = False) -> str:
    """Get complete pipeline state in one call.

    Args:
        full: If True, show all jobs. If False (default), show only jobs with activity.

    Returns terse format:
        Line 1: active:N|archived:N|inbox:N|scraped:N|researched:N|applying:N
        Line 2: verdicts: pursue=N maybe=N skip=N
        Lines 3+: Grouped by stage with headers, then id|company|title|verdict|fit|jd|dive|app
    """
    # Get all data
    jobs_result = http.get("/api/jobs", params={"slim": "true"})
    jobs_archived = http.get("/api/jobs", params={"slim": "true", "include_archived": "true"})
    dives_result = http.get("/api/deep-dives", params={"slim": "true"})
    apps_result = http.get("/api/applications")

    active_jobs = [j for j in jobs_result.get("jobs", []) if not j.get("archived")]
    archived_count = len(jobs_archived.get("jobs", [])) - len(active_jobs)
    dives = {d.get("job_id"): d for d in dives_result.get("deep_dives", [])}
    apps = {a.get("job_id"): a for a in apps_result.get("applications", [])}

    # Categorize jobs by stage
    inbox = []      # No JD
    scraped = []    # JD but no dive
    researched = [] # Dive but no app
    applying = []   # Has app

    # Count verdicts
    verdict_counts = {"pursue": 0, "maybe": 0, "skip": 0}

    for j in active_jobs:
        jid = j.get("job_id", "")
        has_jd = j.get("has_jd") or j.get("jd_text")
        has_dive = jid in dives
        has_app = jid in apps
        verdict = (j.get("verdict") or "").lower()

        if verdict in verdict_counts:
            verdict_counts[verdict] += 1

        if has_app:
            applying.append(j)
        elif has_dive:
            researched.append(j)
        elif has_jd:
            scraped.append(j)
        else:
            inbox.append(j)

    # Summary lines
    lines = [
        f"active:{len(active_jobs)}|archived:{archived_count}|inbox:{len(inbox)}|scraped:{len(scraped)}|researched:{len(researched)}|applying:{len(applying)}",
        f"verdicts: pursue={verdict_counts['pursue']} maybe={verdict_counts['maybe']} skip={verdict_counts['skip']}",
    ]

    def format_job(j):
        jid = j.get("job_id", "")
        dive = dives.get(jid)
        app = apps.get(jid)
        fit = "-"
        if dive:
            conclusions = dive.get("conclusions") or {}
            fit = str(conclusions.get("fit_score") or dive.get("fit") or "-")
        return "|".join([
            _short_id(jid),
            _sanitize(j.get("company", "")),
            _sanitize(j.get("title", "")),
            (j.get("verdict") or "-").lower()[:5],
            fit,
            "jd" if j.get("has_jd") or j.get("jd_text") else "-",
            "dive" if dive else "-",
            "app" if app else "-",
        ])

    if full:
        # Show all jobs, grouped by stage
        if applying:
            lines.append(f"--- Applying ({len(applying)}) ---")
            lines.extend(format_job(j) for j in applying)
        if researched:
            lines.append(f"--- Researched ({len(researched)}) ---")
            lines.extend(format_job(j) for j in researched)
        if scraped:
            lines.append(f"--- Scraped ({len(scraped)}) ---")
            lines.extend(format_job(j) for j in scraped)
        if inbox:
            lines.append(f"--- Inbox ({len(inbox)}) ---")
            lines.extend(format_job(j) for j in inbox)
    else:
        # Show only jobs with activity (dive, app, or verdict)
        active_researched = [j for j in researched if j.get("verdict")]
        if applying:
            lines.append(f"--- Applying ({len(applying)}) ---")
            lines.extend(format_job(j) for j in applying)
        if active_researched:
            lines.append(f"--- Researched ({len(active_researched)}) ---")
            lines.extend(format_job(j) for j in active_researched)

    return "\n".join(lines)


# --- View Control ---


def set_view(view: str, full: bool = False) -> str | dict:
    """Change the UI view/step: 'select', 'deep_dive', or 'application'."""
    result = http.post("/api/view", json={"view": view})
    if full:
        return result
    return f"View: {view}"


def clear_all(full: bool = False) -> str | dict:
    """Archive all jobs, deep dives, and applications for a fresh start."""
    # Get all active jobs
    jobs_result = http.get("/api/jobs")
    job_ids = [j["job_id"] for j in jobs_result.get("jobs", []) if not j.get("archived")]

    # Get all active dives
    dives_result = http.get("/api/deep-dives")
    dive_job_ids = [d["job_id"] for d in dives_result.get("deep_dives", []) if not d.get("archived")]

    # Get all active apps
    apps_result = http.get("/api/applications")
    app_ids = [a["application_id"] for a in apps_result.get("applications", []) if not a.get("archived")]

    # Archive everything
    jobs_archived = 0
    dives_archived = 0
    apps_archived = 0

    if job_ids:
        result = http.post("/api/jobs/archive", json={"job_ids": job_ids})
        jobs_archived = result.get("archived", 0)

    if dive_job_ids:
        result = http.post("/api/deep-dives/archive", json={"job_ids": dive_job_ids})
        dives_archived = result.get("archived", 0)

    if app_ids:
        result = http.post("/api/applications/archive", json={"application_ids": app_ids})
        apps_archived = result.get("archived", 0)

    if full:
        return {"jobs": jobs_archived, "dives": dives_archived, "apps": apps_archived}
    return f"Cleared: {jobs_archived} jobs, {dives_archived} dives, {apps_archived} apps"
