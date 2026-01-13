"""API routes for job_search.

For complete API documentation including data structures, error codes,
and response formats, see: references/api.md
"""

import json
from datetime import datetime
from pathlib import Path
from typing import Optional

from fastapi import APIRouter
from pydantic import BaseModel, Field

from scripts.linkedin_auth import check_auth_status, do_login as linkedin_login
from scripts.linkedin_search import search_linkedin as do_search, get_search_results as get_cached_search, scrape_top_picks as do_top_picks
from scripts.linkedin_jd import scrape_jd as do_scrape_jd, scrape_jds as do_scrape_jds
from scripts.jobscz_search import search_jobscz as do_search_jobscz
from scripts.jobscz_jd import scrape_jd as do_scrape_jd_cz, scrape_jds as do_scrape_jds_cz
from scripts.startupjobs_search import search_startupjobs as do_search_startupjobs
from scripts.startupjobs_jd import scrape_jd as do_scrape_jd_sj, scrape_jds as do_scrape_jds_sj
from scripts.euremotejobs_search import search_euremotejobs as do_search_euremotejobs
from scripts.euremotejobs_jd import scrape_jd as do_scrape_jd_er, scrape_jds as do_scrape_jds_er
from server.utils import generate_job_id, categorize_level, has_ai_focus, compute_days_ago, is_stale, normalize_job_id
from server.data import (
    get_results, save_results, SearchResults, SearchParams, Job as DataJob,
    save_selections, Selections,
    select_jobs as data_select_jobs, deselect_jobs as data_deselect_jobs,
    get_selections_by_source,
    get_deep_dives, get_deep_dive_by_id, save_deep_dive, DeepDive, DeepDives,
    remove_jobs as data_remove_jobs, remove_deep_dives, update_job as data_update_job,
    delete_deep_dive, archive_deep_dives, unarchive_deep_dives,
    Research, Insights, Conclusions, Recommendations, ResearchNotes,
    _write_json, DEEP_DIVES_FILE, JobNotFoundError,
    get_notes as data_get_notes, add_note as data_add_note, remove_note as data_remove_note,
    get_jobs_by_ids, find_company_research,
)
from server.websocket import (
    broadcast_jobs_updated,
    broadcast_deep_dive_updated,
    broadcast_deep_dives_changed,
    broadcast_view_changed,
)

router = APIRouter(prefix="/api")


# --- Slim Serializers (for Claude Desktop token efficiency) ---


def serialize_job_slim(job_data: dict, dive: "DeepDive | None") -> dict:
    """Flat, minimal job representation for tool responses."""
    result = {
        "job_id": job_data["job_id"],
        "title": job_data["title"],
        "company": job_data["company"],
        "loc": job_data.get("location") or "",
        "level": job_data.get("level") or "other",
        "ai": job_data.get("ai_focus", False),
        "has_jd": bool(job_data.get("jd_text")),
    }
    if dive:
        result["verdict"] = dive.recommendations.verdict if dive.recommendations else None
        result["fit"] = dive.conclusions.fit_score if dive.conclusions else None
        result["status"] = dive.status
    return result


def serialize_dive_slim(dive: "DeepDive", job_lookup: dict) -> dict:
    """Flat, minimal deep dive representation."""
    job = job_lookup.get(dive.job_id, {})
    result = {
        "job_id": dive.job_id,
        "company": job.get("company", ""),
        "title": job.get("title", ""),
        "status": dive.status,
    }
    if dive.recommendations:
        result["verdict"] = dive.recommendations.verdict
    if dive.conclusions:
        result["fit"] = dive.conclusions.fit_score
        # Semicolon-delimited for easy parsing, no nested lists
        if dive.conclusions.concerns:
            result["concerns"] = ";".join(dive.conclusions.concerns[:3])
        if dive.conclusions.attractions:
            result["attractions"] = ";".join(dive.conclusions.attractions[:3])
    return result


# --- Request/Response Models ---


class SelectionsRequest(BaseModel):
    selected_ids: list[str]


class PushJobsRequest(BaseModel):
    jobs: list[dict]
    search_params: Optional[dict] = None


class RemoveJobsRequest(BaseModel):
    ids: list[str]


class UpdateJobRequest(BaseModel):
    """Partial update for job fields."""
    title: Optional[str] = None
    company: Optional[str] = None
    location: Optional[str] = None
    salary: Optional[str] = None
    url: Optional[str] = None
    source: Optional[str] = None
    level: Optional[str] = None
    ai_focus: Optional[bool] = None
    posted: Optional[str] = None
    days_ago: Optional[int] = None
    priority: Optional[str] = None
    stage: Optional[str] = None
    verdict: Optional[str] = None
    archived: Optional[bool] = None


class IngestJobsRequest(BaseModel):
    jobs: list[dict]
    dedupe_by: str = "job_id"  # "job_id", "title_company", "none"


class DeepDiveRequest(BaseModel):
    job_id: str
    research: dict = Field(default_factory=dict)
    research_notes: Optional[dict] = None  # Structured findings with sources
    insights: dict = Field(default_factory=dict)
    conclusions: dict = Field(default_factory=dict)
    recommendations: dict = Field(default_factory=dict)


# --- Routes ---


@router.get("/jobs")
def get_jobs(ids: Optional[str] = None, include_archived: bool = False, slim: bool = False):
    """Get current job list with deep_dive data joined.

    Args:
        slim: If True, return flat minimal response for tool calls (no jd_text, no nested deep_dive).
    """
    results = get_results()
    jobs = results.jobs

    # Filter archived unless explicitly included
    if not include_archived:
        jobs = [j for j in jobs if not j.archived]

    if ids:
        id_list = [i.strip() for i in ids.split(",")]
        jobs = [j for j in jobs if j.job_id in id_list]

    # Build deep_dive lookup for efficient joining
    dives = get_deep_dives()
    dive_lookup = {d.job_id: d for d in dives.deep_dives}

    # Slim mode: flat minimal response
    if slim:
        jobs_out = []
        for job in jobs:
            dive = dive_lookup.get(job.job_id)
            jobs_out.append(serialize_job_slim(job.model_dump(), dive))
        jobs_out.sort(key=lambda j: (j.get("sort_order") is None, j.get("sort_order") or 0))
        return {"status": "ok", "jobs": jobs_out, "total": len(jobs_out)}

    # Full mode: join deep_dive data to each job
    jobs_with_dives = []
    for job in jobs:
        job_data = job.model_dump()
        # Compute days_ago dynamically from posted date
        if job_data.get("posted"):
            job_data["days_ago"] = compute_days_ago(job_data["posted"])
        # Compute staleness
        job_data["stale"] = is_stale(job_data.get("posted"), job_data.get("ingested_at"))
        dive = dive_lookup.get(job.job_id)
        job_data["deep_dive"] = dive.model_dump() if dive else None
        jobs_with_dives.append(job_data)

    # Sort by sort_order (None values go to end)
    jobs_with_dives.sort(key=lambda j: (j.get("sort_order") is None, j.get("sort_order") or 0))

    return {"status": "ok", "jobs": jobs_with_dives, "total": len(jobs_with_dives)}


@router.get("/jobs/{job_id}")
def get_job(job_id: str):
    """Get a single job by ID, with deep_dive data joined if exists."""
    job_id = normalize_job_id(job_id)
    results = get_results()
    job = next((j for j in results.jobs if j.job_id == job_id), None)
    if not job:
        return {"status": "error", "error": "Job not found", "code": "JOB_NOT_FOUND"}

    # Join deep_dive data from separate file
    job_data = job.model_dump()
    # Compute days_ago dynamically from posted date
    if job_data.get("posted"):
        job_data["days_ago"] = compute_days_ago(job_data["posted"])
    # Compute staleness
    job_data["stale"] = is_stale(job_data.get("posted"), job_data.get("ingested_at"))
    deep_dive = get_deep_dive_by_id(job_id)
    job_data["deep_dive"] = deep_dive.model_dump() if deep_dive else None

    return {"status": "ok", "job": job_data}


@router.post("/jobs")
def push_jobs(req: PushJobsRequest):
    """Push curated job list to UI (replaces existing jobs)."""
    try:
        # Clear dependent state since we're replacing the job list
        # (selections and deep dives reference job IDs that won't exist)
        save_selections(Selections(selected_ids=[]))
        _write_json(DEEP_DIVES_FILE, DeepDives().model_dump())

        # Convert job dicts to DataJob models
        jobs = []
        for j in req.jobs:
            posted = j.get("posted")
            jobs.append(DataJob(
                job_id=j.get("job_id", generate_job_id(j.get("url", ""), j.get("title", ""), j.get("company", ""))),
                title=j.get("title", ""),
                company=j.get("company", ""),
                location=j.get("location"),
                salary=j.get("salary"),
                url=j.get("url", ""),
                source=j.get("source", "unknown"),
                level=j.get("level") or categorize_level(j.get("title", "")),
                ai_focus=j.get("ai_focus") if j.get("ai_focus") is not None else has_ai_focus(j.get("title", "")),
                posted=posted,
                days_ago=j.get("days_ago") if j.get("days_ago") is not None else compute_days_ago(posted),
                # Workflow fields
                priority=j.get("priority"),
                stage=j.get("stage"),
                verdict=j.get("verdict"),
                archived=j.get("archived", False),
                sort_order=j.get("sort_order"),
                # JD fields
                jd_text=j.get("jd_text"),
                jd_scraped_at=j.get("jd_scraped_at"),
                # Ingest tracking
                ingested_at=j.get("ingested_at") or datetime.utcnow().isoformat() + "Z",
            ))

        # Build search params from request or defaults
        params = req.search_params or {}
        results = SearchResults(
            search_params=SearchParams(
                query=params.get("query", "curated"),
                location=params.get("location"),
                days=params.get("days"),
                sites=params.get("sites", []),
                n=len(jobs),
                remote=params.get("remote"),
                timestamp=datetime.utcnow().isoformat() + "Z",
            ),
            jobs=jobs,
        )
        save_results(results)
        broadcast_jobs_updated()

        return {"status": "ok", "job_count": len(jobs)}

    except Exception as e:
        return {"status": "error", "error": str(e), "code": "INTERNAL_ERROR"}


@router.post("/jobs/ingest")
def ingest_jobs(req: IngestJobsRequest):
    """Add jobs with server-side deduplication."""
    try:
        existing = get_results()
        existing_jobs = {j.job_id: j for j in existing.jobs}

        # Build dedupe keys for existing jobs
        existing_keys: set[str] = set()
        if req.dedupe_by == "job_id":
            existing_keys = set(existing_jobs.keys())
        elif req.dedupe_by == "title_company":
            existing_keys = {
                f"{j.title.lower().strip()}:{j.company.lower().strip()}"
                for j in existing.jobs
            }

        added = []
        skipped = []

        for j in req.jobs:
            # Generate ID if not provided
            job_id = j.get("job_id", generate_job_id(
                j.get("url", ""), j.get("title", ""), j.get("company", "")
            ))

            # Check for duplicates based on strategy
            if req.dedupe_by == "job_id":
                dedupe_key = job_id
            elif req.dedupe_by == "title_company":
                dedupe_key = f"{j.get('title', '').lower().strip()}:{j.get('company', '').lower().strip()}"
            else:
                dedupe_key = None  # No deduplication

            if dedupe_key and dedupe_key in existing_keys:
                skipped.append({"job_id": job_id, "reason": "duplicate"})
                continue

            # Add to existing keys to catch dupes within this batch
            if dedupe_key:
                existing_keys.add(dedupe_key)

            # Convert to DataJob
            posted = j.get("posted")
            new_job = DataJob(
                job_id=job_id,
                title=j.get("title", ""),
                company=j.get("company", ""),
                location=j.get("location"),
                salary=j.get("salary"),
                url=j.get("url", ""),
                source=j.get("source", "unknown"),
                level=j.get("level") or categorize_level(j.get("title", "")),
                ai_focus=j.get("ai_focus") if j.get("ai_focus") is not None else has_ai_focus(j.get("title", "")),
                posted=posted,
                days_ago=j.get("days_ago") if j.get("days_ago") is not None else compute_days_ago(posted),
                # Workflow fields
                priority=j.get("priority"),
                stage=j.get("stage"),
                verdict=j.get("verdict"),
                archived=j.get("archived", False),
                sort_order=j.get("sort_order"),
                # JD fields
                jd_text=j.get("jd_text"),
                jd_scraped_at=j.get("jd_scraped_at"),
                # Ingest tracking
                ingested_at=datetime.utcnow().isoformat() + "Z",
            )
            added.append(new_job)

        # Append new jobs to existing
        if added:
            existing.jobs.extend(added)
            save_results(existing)
            broadcast_jobs_updated()

        return {
            "status": "ok",
            "added": len(added),
            "skipped": len(skipped),
            "skipped_jobs": skipped,
            "total": len(existing.jobs),
        }

    except Exception as e:
        return {"status": "error", "error": str(e), "code": "INTERNAL_ERROR"}


@router.delete("/jobs")
def remove_jobs(req: RemoveJobsRequest):
    """Remove specific jobs from UI by ID."""
    try:
        # Remove jobs from results
        removed_count, not_found = data_remove_jobs(req.ids)

        # Also remove any deep dives for these jobs
        removed_dives = remove_deep_dives(req.ids)

        # Notify UI
        if removed_count > 0:
            broadcast_jobs_updated()

        return {
            "status": "ok",
            "removed": removed_count,
            "not_found": not_found,
            "removed_deep_dives": removed_dives,
        }

    except Exception as e:
        return {"status": "error", "error": str(e), "code": "INTERNAL_ERROR"}


@router.patch("/jobs/{job_id}")
def update_job(job_id: str, req: UpdateJobRequest):
    """Update specific fields of an existing job."""
    job_id = normalize_job_id(job_id)
    try:
        # Build updates dict from non-None fields
        updates = {k: v for k, v in req.model_dump().items() if v is not None}

        if not updates:
            return {"status": "error", "error": "No fields to update", "code": "INVALID_PARAM"}

        updated_job = data_update_job(job_id, updates)
        if not updated_job:
            return {"status": "error", "error": "Job not found", "code": "JOB_NOT_FOUND"}

        broadcast_jobs_updated()
        return {"status": "ok", "job_id": job_id, "job": updated_job.model_dump()}

    except Exception as e:
        return {"status": "error", "error": str(e), "code": "INTERNAL_ERROR"}


@router.get("/selections")
def read_selections(source: Optional[str] = None):
    """Get selections, optionally filtered by source."""
    return get_selections_by_source(source)


@router.post("/selections")
def write_selections(req: SelectionsRequest):
    """Save selections (legacy endpoint)."""
    selections = Selections(
        selected_ids=req.selected_ids,
        updated_at=datetime.utcnow().isoformat() + "Z",
    )
    save_selections(selections)
    return {"status": "ok"}


class SelectJobsRequest(BaseModel):
    job_ids: list[str]
    source: str = "claude"


@router.post("/selections/select")
def select_jobs(req: SelectJobsRequest):
    """Select jobs with source attribution."""
    job_ids = [normalize_job_id(jid) for jid in req.job_ids]
    result = data_select_jobs(job_ids, req.source)
    if result.get("status") == "ok":
        broadcast_jobs_updated()
    return result


class DeselectJobsRequest(BaseModel):
    job_ids: list[str]


@router.post("/selections/deselect")
def deselect_jobs(req: DeselectJobsRequest):
    """Deselect jobs."""
    job_ids = [normalize_job_id(jid) for jid in req.job_ids]
    result = data_deselect_jobs(job_ids)
    broadcast_jobs_updated()
    return result


@router.get("/deep-dives")
def read_deep_dives(include_archived: bool = False, slim: bool = False):
    """Get all deep dives.

    Args:
        slim: If True, return flat minimal response for tool calls.
    """
    dives = get_deep_dives()
    if not include_archived:
        dives.deep_dives = [d for d in dives.deep_dives if not d.archived]

    # Slim mode: flat minimal response with job context
    if slim:
        results = get_results()
        job_lookup = {j.job_id: j.model_dump() for j in results.jobs}
        return {
            "status": "ok",
            "deep_dives": [serialize_dive_slim(d, job_lookup) for d in dives.deep_dives],
            "total": len(dives.deep_dives),
        }

    return dives


@router.post("/deep-dives")
def write_deep_dive(req: DeepDiveRequest):
    """Save a deep dive for a job and set job stage to 'deep_dive'."""
    job_id = normalize_job_id(req.job_id)
    deep_dive = DeepDive(
        job_id=job_id,
        status="complete",
        updated_at=datetime.utcnow().isoformat() + "Z",
        research=Research.model_validate(req.research) if req.research else Research(),
        research_notes=ResearchNotes.model_validate(req.research_notes) if req.research_notes else None,
        insights=Insights.model_validate(req.insights) if req.insights else Insights(),
        conclusions=Conclusions.model_validate(req.conclusions) if req.conclusions else Conclusions(),
        recommendations=Recommendations.model_validate(req.recommendations) if req.recommendations else Recommendations(),
    )
    try:
        save_deep_dive(deep_dive)
        # Also set job stage to 'deep_dive' so UI shows it in Deep Dives view
        data_update_job(job_id, {"stage": "deep_dive"})
    except JobNotFoundError as e:
        return {"status": "error", "error": str(e), "code": "JOB_NOT_FOUND"}
    broadcast_deep_dive_updated(job_id)
    broadcast_jobs_updated()
    broadcast_view_changed("deep_dives")
    return {"status": "ok", "job_id": job_id}


class DeepDivePatchRequest(BaseModel):
    """Partial update for deep dive fields."""
    jd: Optional[dict] = None
    enhanced_insights: Optional[dict] = None
    research: Optional[dict] = None
    research_notes: Optional[dict] = None  # Structured findings with sources
    insights: Optional[dict] = None
    conclusions: Optional[dict] = None
    recommendations: Optional[dict] = None
    status: Optional[str] = None


@router.patch("/deep-dives/{job_id}")
def patch_deep_dive(job_id: str, req: DeepDivePatchRequest):
    """Update specific fields of an existing deep dive."""
    job_id = normalize_job_id(job_id)
    existing = get_deep_dive_by_id(job_id)
    if not existing:
        return {"status": "error", "error": "Deep dive not found", "code": "DEEP_DIVE_NOT_FOUND"}

    # Merge updates into existing data
    update_data = existing.model_dump()
    update_data["updated_at"] = datetime.utcnow().isoformat() + "Z"

    if req.jd is not None:
        update_data["jd"] = req.jd
    if req.enhanced_insights is not None:
        update_data["enhanced_insights"] = req.enhanced_insights
    if req.research is not None:
        update_data["research"] = {**update_data.get("research", {}), **req.research}
    if req.research_notes is not None:
        update_data["research_notes"] = req.research_notes
    if req.insights is not None:
        update_data["insights"] = {**update_data.get("insights", {}), **req.insights}
    if req.conclusions is not None:
        update_data["conclusions"] = {**update_data.get("conclusions", {}), **req.conclusions}
    if req.recommendations is not None:
        update_data["recommendations"] = {**update_data.get("recommendations", {}), **req.recommendations}
    if req.status is not None:
        update_data["status"] = req.status

    updated_dive = DeepDive.model_validate(update_data)
    try:
        save_deep_dive(updated_dive)
    except JobNotFoundError as e:
        return {"status": "error", "error": str(e), "code": "JOB_NOT_FOUND"}
    broadcast_deep_dive_updated(job_id)
    return {"status": "ok", "job_id": job_id}


@router.delete("/deep-dives/{job_id}")
def delete_deep_dive_route(job_id: str):
    """Delete a deep dive by job ID."""
    job_id = normalize_job_id(job_id)
    success = delete_deep_dive(job_id)
    if not success:
        return {"status": "error", "error": "Deep dive not found", "code": "NOT_FOUND"}
    broadcast_deep_dives_changed()
    return {"status": "ok", "deleted": job_id}


class DeleteDeepDivesRequest(BaseModel):
    job_ids: list[str]


@router.post("/deep-dives/delete")
def delete_deep_dives_route(req: DeleteDeepDivesRequest):
    """Delete multiple deep dives by job IDs."""
    job_ids = [normalize_job_id(jid) for jid in req.job_ids]
    deleted = 0
    not_found = []
    for job_id in job_ids:
        if delete_deep_dive(job_id):
            deleted += 1
        else:
            not_found.append(job_id)
    if deleted > 0:
        broadcast_deep_dives_changed()
    return {"status": "ok", "deleted": deleted, "not_found": not_found}


class ArchiveDeepDivesRequest(BaseModel):
    job_ids: list[str]


@router.post("/deep-dives/archive")
def archive_deep_dives_route(req: ArchiveDeepDivesRequest):
    """Archive deep dives by job IDs."""
    job_ids = [normalize_job_id(jid) for jid in req.job_ids]
    archived, not_found = archive_deep_dives(job_ids)
    if archived > 0:
        broadcast_deep_dives_changed()
    return {"status": "ok", "archived": archived, "not_found": not_found}


@router.post("/deep-dives/unarchive")
def unarchive_deep_dives_route(req: ArchiveDeepDivesRequest):
    """Unarchive deep dives by job IDs."""
    job_ids = [normalize_job_id(jid) for jid in req.job_ids]
    unarchived, not_found = unarchive_deep_dives(job_ids)
    if unarchived > 0:
        broadcast_deep_dives_changed()
    return {"status": "ok", "unarchived": unarchived, "not_found": not_found}


# --- Knowledge Routes ---


@router.get("/knowledge/company/{company_name:path}")
def get_company_knowledge(company_name: str):
    """Return existing research for company from prior deep dives."""
    return find_company_research(company_name)


# --- Status & Auth Routes ---


@router.get("/status")
def server_status():
    """Combined health check: server + LinkedIn auth."""
    auth = check_auth_status()
    result = {
        "status": "ok",
        "server": "running",
        "linkedin_auth": auth.get("authenticated", False),
        "linkedin_user": auth.get("user"),
    }
    # Surface auth errors (e.g., SELECTOR_BROKEN)
    if auth.get("status") == "error":
        result["auth_error"] = auth.get("error")
        result["auth_code"] = auth.get("code")
    return result


@router.get("/auth/status")
def auth_status():
    """Check LinkedIn authentication status."""
    return check_auth_status()


@router.post("/auth/login")
def login():
    """Open browser for LinkedIn login. Blocks until complete or timeout."""
    return linkedin_login()


# --- Search Routes ---


def _get_existing_job_keys() -> tuple[set[str], set[str]]:
    """Return (job_ids, title_company_keys) for deduplication."""
    existing = get_results()
    job_ids = {j.job_id for j in existing.jobs}
    title_keys = {f"{j.title.lower().strip()}:{j.company.lower().strip()}" for j in existing.jobs}
    return job_ids, title_keys


def _filter_existing(jobs: list[dict], job_ids: set[str], title_keys: set[str]) -> list[dict]:
    """Remove jobs that match existing board entries."""
    result = []
    for job in jobs:
        if job.get("job_id") in job_ids:
            continue
        key = f"{job.get('title', '').lower().strip()}:{job.get('company', '').lower().strip()}"
        if key in title_keys:
            continue
        result.append(job)
    return result


class SearchRequest(BaseModel):
    query: str
    region: Optional[str] = None
    location: Optional[str] = None
    remote: Optional[bool] = None
    days: int = 30
    max_pages: int = 3
    exclude_locations: Optional[list[str]] = None
    exclude_companies: Optional[list[str]] = None
    min_level: Optional[str] = None
    ai_only: bool = False
    exclude_existing: bool = True  # Filter out jobs already on the board


@router.post("/search/linkedin")
def search_linkedin(req: SearchRequest):
    """Search LinkedIn jobs with filtering and region presets."""
    result = do_search(
        query=req.query,
        region=req.region,
        remote=req.remote,
        days=req.days,
        max_pages=req.max_pages,
        exclude_locations=req.exclude_locations,
        exclude_companies=req.exclude_companies,
        min_level=req.min_level,
        ai_only=req.ai_only,
    )
    if req.exclude_existing and result.get("status") == "ok":
        job_ids, title_keys = _get_existing_job_keys()
        original_count = len(result.get("jobs", []))
        result["jobs"] = _filter_existing(result.get("jobs", []), job_ids, title_keys)
        result["excluded_existing"] = original_count - len(result["jobs"])
    return result


@router.get("/search/{search_id}")
def get_search(search_id: str):
    """Retrieve cached search results."""
    return get_cached_search(search_id)


class TopPicksRequest(BaseModel):
    exclude_locations: Optional[list[str]] = None
    exclude_companies: Optional[list[str]] = None
    min_level: Optional[str] = None
    ai_only: bool = False
    exclude_existing: bool = True


@router.post("/linkedin/top-picks")
def linkedin_top_picks(req: TopPicksRequest):
    """Scrape LinkedIn's personalized 'Top job picks for you'."""
    result = do_top_picks(
        exclude_locations=req.exclude_locations,
        exclude_companies=req.exclude_companies,
        min_level=req.min_level,
        ai_only=req.ai_only,
    )
    if req.exclude_existing and result.get("status") == "ok":
        job_ids, title_keys = _get_existing_job_keys()
        original_count = len(result.get("jobs", []))
        result["jobs"] = _filter_existing(result.get("jobs", []), job_ids, title_keys)
        result["excluded_existing"] = original_count - len(result["jobs"])
        result["job_count"] = len(result["jobs"])
    return result


class JobsCzSearchRequest(BaseModel):
    query: str
    location: Optional[str] = None
    remote: Optional[str] = None  # "remote", "hybrid", "flexible"
    days: int = 30
    max_pages: int = 3
    exclude_locations: Optional[list[str]] = None
    exclude_companies: Optional[list[str]] = None
    min_level: Optional[str] = None
    ai_only: bool = False
    exclude_existing: bool = True  # Filter out jobs already on the board


@router.post("/search/jobscz")
def search_jobscz(req: JobsCzSearchRequest):
    """Search jobs.cz for Czech job listings."""
    result = do_search_jobscz(
        query=req.query,
        location=req.location,
        remote=req.remote,
        days=req.days,
        max_pages=req.max_pages,
        exclude_locations=req.exclude_locations,
        exclude_companies=req.exclude_companies,
        min_level=req.min_level,
        ai_only=req.ai_only,
    )
    if req.exclude_existing and result.get("status") == "ok":
        job_ids, title_keys = _get_existing_job_keys()
        original_count = len(result.get("jobs", []))
        result["jobs"] = _filter_existing(result.get("jobs", []), job_ids, title_keys)
        result["excluded_existing"] = original_count - len(result["jobs"])
    return result


class StartupJobsSearchRequest(BaseModel):
    query: str
    location: Optional[str] = None
    remote: Optional[str] = None  # "remote", "hybrid", "onsite"
    seniority: Optional[str] = None  # "junior", "medior", "senior"
    days: int = 30
    limit: int = 50
    exclude_locations: Optional[list[str]] = None
    exclude_companies: Optional[list[str]] = None
    min_level: Optional[str] = None
    ai_only: bool = False
    exclude_existing: bool = True  # Filter out jobs already on the board


@router.post("/search/startupjobs")
def search_startupjobs(req: StartupJobsSearchRequest):
    """Search startupjobs.cz for Czech startup job listings."""
    result = do_search_startupjobs(
        query=req.query,
        location=req.location,
        remote=req.remote,
        seniority=req.seniority,
        days=req.days,
        limit=req.limit,
        exclude_locations=req.exclude_locations,
        exclude_companies=req.exclude_companies,
        min_level=req.min_level,
        ai_only=req.ai_only,
    )
    if req.exclude_existing and result.get("status") == "ok":
        job_ids, title_keys = _get_existing_job_keys()
        original_count = len(result.get("jobs", []))
        result["jobs"] = _filter_existing(result.get("jobs", []), job_ids, title_keys)
        result["excluded_existing"] = original_count - len(result["jobs"])
    return result


# --- Unified Search (search + filter + ingest) ---


FILTERS_FILE = Path(__file__).parent.parent.parent / "data" / "profile" / "search-filters.json"


def _load_search_filters() -> dict:
    """Load user's search filters from JSON file."""
    if FILTERS_FILE.exists():
        try:
            return json.loads(FILTERS_FILE.read_text())
        except (json.JSONDecodeError, IOError):
            pass
    return {}


def _apply_hard_filters(jobs: list[dict], filters: dict) -> tuple[list[dict], int]:
    """Apply hard filters from search-filters.json. Returns (filtered_jobs, filtered_count)."""
    title_must_contain = [t.lower() for t in filters.get("title_must_contain", [])]
    exclude_levels = [lv.lower() for lv in filters.get("exclude_levels", [])]
    include_locations = [loc.lower() for loc in filters.get("include_locations", [])]
    exclude_companies = [c.lower() for c in filters.get("exclude_companies", [])]

    result = []
    filtered = 0

    # Czech job boards are inherently in Czech Republic - bypass location filter
    czech_sources = {"jobs.cz", "startupjobs.cz"}

    for job in jobs:
        title = (job.get("title") or "").lower()
        level = (job.get("level") or "").lower()
        location = (job.get("location") or "").lower()
        company = (job.get("company") or "").lower()
        source = job.get("source") or ""

        # Title must contain at least one of the required terms
        if title_must_contain and not any(term in title for term in title_must_contain):
            filtered += 1
            continue

        # Exclude certain levels
        if level in exclude_levels:
            filtered += 1
            continue

        # Location must match at least one allowed location (whitelist)
        # Skip for Czech job boards - they're inherently in Czech Republic
        if source not in czech_sources:
            if include_locations and not any(loc in location for loc in include_locations):
                filtered += 1
                continue

        # Exclude companies (exact match)
        if company in exclude_companies:
            filtered += 1
            continue

        result.append(job)

    return result, filtered


class UnifiedSearchRequest(BaseModel):
    query: str
    location: Optional[str] = None  # "Prague", "Remote EU", etc.
    sources: list[str] = ["linkedin"]  # Add regional: euremotejobs (EU/Italy), jobscz+startupjobs (CZ)
    days: int = 30
    # Optional overrides (bypass search-filters.json for edge cases)
    skip_filters: bool = False


@router.post("/search")
def unified_search(req: UnifiedSearchRequest):
    """Search, filter, and ingest jobs in one call.

    1. Search across specified sources
    2. Apply hard filters from search-filters.json
    3. Dedupe against existing board
    4. Auto-ingest filtered results
    5. Return summary
    """
    all_jobs = []
    errors = []

    # Search each source
    for source in req.sources:
        if source == "linkedin":
            result = do_search(query=req.query, region=req.location, days=req.days)
        elif source == "jobscz":
            result = do_search_jobscz(query=req.query, location=req.location, days=req.days)
        elif source == "startupjobs":
            result = do_search_startupjobs(query=req.query, location=req.location, days=req.days)
        elif source == "euremotejobs":
            result = do_search_euremotejobs(query=req.query, location=req.location, days=req.days)
        else:
            errors.append(f"Unknown source: {source}")
            continue

        if result.get("status") == "error":
            errors.append(f"{source}: {result.get('error', 'Unknown error')}")
        else:
            all_jobs.extend(result.get("jobs", []))

    if not all_jobs:
        return {
            "status": "ok",
            "added": 0,
            "filtered": 0,
            "duplicates": 0,
            "total_found": 0,
            "errors": errors if errors else None,
        }

    total_found = len(all_jobs)

    # Apply hard filters from search-filters.json
    filtered_count = 0
    if not req.skip_filters:
        filters = _load_search_filters()
        if filters:
            all_jobs, filtered_count = _apply_hard_filters(all_jobs, filters)

    # Dedupe against existing board
    job_ids, title_keys = _get_existing_job_keys()
    before_dedupe = len(all_jobs)
    all_jobs = _filter_existing(all_jobs, job_ids, title_keys)
    duplicates = before_dedupe - len(all_jobs)

    # Auto-ingest remaining jobs
    added = 0
    if all_jobs:
        existing = get_results()
        for j in all_jobs:
            posted = j.get("posted")
            new_job = DataJob(
                job_id=j.get("job_id", generate_job_id(j.get("url", ""), j.get("title", ""), j.get("company", ""))),
                title=j.get("title", ""),
                company=j.get("company", ""),
                location=j.get("location"),
                salary=j.get("salary"),
                url=j.get("url", ""),
                source=j.get("source", "unknown"),
                level=j.get("level") or categorize_level(j.get("title", "")),
                ai_focus=j.get("ai_focus") if j.get("ai_focus") is not None else has_ai_focus(j.get("title", "")),
                posted=posted,
                days_ago=j.get("days_ago") if j.get("days_ago") is not None else compute_days_ago(posted),
                ingested_at=datetime.utcnow().isoformat() + "Z",
            )
            existing.jobs.append(new_job)
            added += 1
        save_results(existing)
        broadcast_jobs_updated()

    return {
        "status": "ok",
        "added": added,
        "filtered": filtered_count,
        "duplicates": duplicates,
        "total_found": total_found,
        "errors": errors if errors else None,
    }


# --- JD Scrape Routes ---


@router.get("/jd/{job_id}")
def scrape_jd(job_id: str):
    """Scrape job description from LinkedIn and persist to job record."""
    job_id = normalize_job_id(job_id)
    result = do_scrape_jd(job_id)
    if result.get("status") == "ok":
        # Persist JD and posting date to job record
        update_fields = {
            "jd_text": result["jd_text"],
            "jd_scraped_at": result["scraped_at"],
        }
        if result.get("posted"):
            update_fields["posted"] = result["posted"]
        data_update_job(result["job_id"], update_fields)
        broadcast_jobs_updated()
    return result


class ScrapeJdsRequest(BaseModel):
    job_ids: list[str]


@router.post("/jd/batch")
def scrape_jds(req: ScrapeJdsRequest):
    """Batch scrape job descriptions from LinkedIn and persist to job records."""
    job_ids = [normalize_job_id(jid) for jid in req.job_ids]
    result = do_scrape_jds(job_ids)
    if result.get("status") == "ok":
        # Persist each successful JD and posting date to job record
        for item in result.get("results", []):
            if item.get("jd_text"):
                update_fields = {
                    "jd_text": item["jd_text"],
                    "jd_scraped_at": item["scraped_at"],
                }
                if item.get("posted"):
                    update_fields["posted"] = item["posted"]
                data_update_job(item["job_id"], update_fields)
        broadcast_jobs_updated()
    return result


# --- Jobs.cz JD Scrape Routes ---


@router.get("/jd-cz/{job_id}")
def scrape_jd_cz(job_id: str):
    """Scrape job description from jobs.cz and persist to job record."""
    job_id = normalize_job_id(job_id)
    # Look up stored URL - scraper needs it (can't construct from ID alone)
    jobs = get_jobs_by_ids([job_id])
    scrape_input = jobs[0].url if jobs and jobs[0].url else job_id
    result = do_scrape_jd_cz(scrape_input)
    if result.get("status") == "ok":
        update_fields = {
            "jd_text": result["jd_text"],
            "jd_scraped_at": result["scraped_at"],
        }
        if result.get("posted"):
            update_fields["posted"] = result["posted"]
        data_update_job(result["job_id"], update_fields)
        broadcast_jobs_updated()
    return result


@router.post("/jd-cz/batch")
def scrape_jds_cz(req: ScrapeJdsRequest):
    """Batch scrape job descriptions from jobs.cz and persist to job records."""
    job_ids = [normalize_job_id(jid) for jid in req.job_ids]
    # Look up stored URLs - scraper needs them (can't construct from ID alone)
    jobs = get_jobs_by_ids(job_ids)
    url_map = {j.job_id: j.url for j in jobs if j.url}
    scrape_inputs = [url_map.get(jid, jid) for jid in req.job_ids]
    result = do_scrape_jds_cz(scrape_inputs)
    if result.get("status") == "ok":
        for item in result.get("results", []):
            if item.get("jd_text"):
                update_fields = {
                    "jd_text": item["jd_text"],
                    "jd_scraped_at": item["scraped_at"],
                }
                if item.get("posted"):
                    update_fields["posted"] = item["posted"]
                data_update_job(item["job_id"], update_fields)
        broadcast_jobs_updated()
    return result


# --- StartupJobs.cz JD Scrape Routes ---


@router.get("/jd-sj/{job_id}")
def scrape_jd_sj(job_id: str):
    """Scrape job description from startupjobs.cz and persist to job record."""
    job_id = normalize_job_id(job_id)
    result = do_scrape_jd_sj(job_id)
    if result.get("status") == "ok":
        data_update_job(result["job_id"], {
            "jd_text": result["jd_text"],
            "jd_scraped_at": result["scraped_at"],
        })
        broadcast_jobs_updated()
    return result


@router.post("/jd-sj/batch")
def scrape_jds_sj(req: ScrapeJdsRequest):
    """Batch scrape job descriptions from startupjobs.cz and persist to job records."""
    job_ids = [normalize_job_id(jid) for jid in req.job_ids]
    result = do_scrape_jds_sj(job_ids)
    if result.get("status") == "ok":
        for item in result.get("results", []):
            if item.get("jd_text"):
                data_update_job(item["job_id"], {
                    "jd_text": item["jd_text"],
                    "jd_scraped_at": item["scraped_at"],
                })
        broadcast_jobs_updated()
    return result


# --- EU Remote Jobs JD Scrape Routes ---


@router.get("/jd-er/{job_id}")
def scrape_jd_er(job_id: str):
    """Scrape job description from euremotejobs.com and persist to job record."""
    job_id = normalize_job_id(job_id)
    result = do_scrape_jd_er(job_id)
    if result.get("status") == "ok":
        data_update_job(result["job_id"], {
            "jd_text": result["jd_text"],
            "jd_scraped_at": result["scraped_at"],
        })
        broadcast_jobs_updated()
    return result


@router.post("/jd-er/batch")
def scrape_jds_er(req: ScrapeJdsRequest):
    """Batch scrape job descriptions from euremotejobs.com and persist to job records."""
    job_ids = [normalize_job_id(jid) for jid in req.job_ids]
    result = do_scrape_jds_er(job_ids)
    if result.get("status") == "ok":
        for item in result.get("results", []):
            if item.get("jd_text"):
                data_update_job(item["job_id"], {
                    "jd_text": item["jd_text"],
                    "jd_scraped_at": item["scraped_at"],
                })
        broadcast_jobs_updated()
    return result


# --- Notes Routes ---


class AddNoteRequest(BaseModel):
    job_id: str
    text: str


@router.post("/notes")
def add_note(req: AddNoteRequest):
    """Add a note for a job."""
    job_id = normalize_job_id(req.job_id)
    try:
        note = data_add_note(job_id, req.text)
        broadcast_jobs_updated()
        return {"status": "ok", "note_id": note.note_id, "job_id": note.job_id}
    except JobNotFoundError as e:
        return {"status": "error", "error": str(e), "code": "JOB_NOT_FOUND"}


@router.delete("/notes/{note_id}")
def remove_note(note_id: str):
    """Remove a note by ID."""
    if data_remove_note(note_id):
        broadcast_jobs_updated()
        return {"status": "ok"}
    return {"status": "error", "error": "Note not found", "code": "NOTE_NOT_FOUND"}


@router.get("/notes/{job_id}")
def get_notes(job_id: str):
    """Get notes for a job."""
    job_id = normalize_job_id(job_id)
    notes = data_get_notes(job_id)
    return {
        "status": "ok",
        "notes": [{"note_id": n.note_id, "text": n.text, "created_at": n.created_at} for n in notes],
    }


# --- Priority, Stage, Verdict Routes ---


class SetPriorityRequest(BaseModel):
    job_id: str
    priority: Optional[str] = None  # "high", "medium", "low", or None to clear


@router.post("/jobs/priority")
def set_priority(req: SetPriorityRequest):
    """Set priority for a job."""
    job_id = normalize_job_id(req.job_id)
    if req.priority and req.priority not in ("high", "medium", "low"):
        return {"status": "error", "error": "Invalid priority. Use: high, medium, low", "code": "INVALID_PARAM"}

    updated_job = data_update_job(job_id, {"priority": req.priority})
    if not updated_job:
        return {"status": "error", "error": "Job not found", "code": "JOB_NOT_FOUND"}

    broadcast_jobs_updated()
    return {"status": "ok", "job_id": req.job_id, "priority": req.priority}


class MoveToStageRequest(BaseModel):
    job_id: str
    stage: str  # "select", "deep_dive", "application"


@router.post("/jobs/stage")
def move_to_stage(req: MoveToStageRequest):
    """Move job to a workflow stage."""
    job_id = normalize_job_id(req.job_id)
    if req.stage not in ("select", "deep_dive", "application"):
        return {"status": "error", "error": "Invalid stage. Use: select, deep_dive, application", "code": "INVALID_PARAM"}

    updated_job = data_update_job(job_id, {"stage": req.stage})
    if not updated_job:
        return {"status": "error", "error": "Job not found", "code": "JOB_NOT_FOUND"}

    broadcast_jobs_updated()
    return {"status": "ok", "job_id": req.job_id, "stage": req.stage}


class SetVerdictRequest(BaseModel):
    job_id: str
    verdict: str  # "Pursue", "Maybe", "Skip"


@router.post("/jobs/verdict")
def set_verdict(req: SetVerdictRequest):
    """Set verdict for a job."""
    job_id = normalize_job_id(req.job_id)
    if req.verdict not in ("Pursue", "Maybe", "Skip"):
        return {"status": "error", "error": "Invalid verdict. Use: Pursue, Maybe, Skip", "code": "INVALID_PARAM"}

    updated_job = data_update_job(job_id, {"verdict": req.verdict})
    if not updated_job:
        return {"status": "error", "error": "Job not found", "code": "JOB_NOT_FOUND"}

    broadcast_jobs_updated()
    return {"status": "ok", "job_id": job_id, "verdict": req.verdict}


# --- Archive Routes ---


class ArchiveJobsRequest(BaseModel):
    job_ids: list[str]


@router.post("/jobs/archive")
def archive_jobs(req: ArchiveJobsRequest):
    """Archive jobs (soft delete)."""
    job_ids = [normalize_job_id(jid) for jid in req.job_ids]
    archived_jobs = []
    not_found = []

    for job_id in job_ids:
        updated = data_update_job(job_id, {"archived": True})
        if updated:
            archived_jobs.append(updated.model_dump())
        else:
            not_found.append(job_id)

    if archived_jobs:
        broadcast_jobs_updated()

    return {"status": "ok", "archived": len(archived_jobs), "jobs": archived_jobs, "not_found": not_found}


@router.post("/jobs/unarchive")
def unarchive_jobs(req: ArchiveJobsRequest):
    """Unarchive jobs. Refuses to unarchive stale jobs."""
    job_ids = [normalize_job_id(jid) for jid in req.job_ids]
    unarchived_jobs = []
    not_found = []
    stale_skipped = []

    # Get all jobs to check staleness
    results = get_results()
    jobs_by_id = {j.job_id: j for j in results.jobs}

    for job_id in job_ids:
        job = jobs_by_id.get(job_id)
        if not job:
            not_found.append(job_id)
            continue

        # Check staleness before unarchiving
        if is_stale(job.posted, job.ingested_at):
            stale_skipped.append(job_id)
            continue

        updated = data_update_job(job_id, {"archived": False})
        if updated:
            unarchived_jobs.append(updated.model_dump())

    if unarchived_jobs:
        broadcast_jobs_updated()

    return {
        "status": "ok",
        "unarchived": len(unarchived_jobs),
        "jobs": unarchived_jobs,
        "not_found": not_found,
        "stale_skipped": stale_skipped,
    }


class MarkDeadRequest(BaseModel):
    job_ids: list[str]


@router.post("/jobs/dead")
def mark_jobs_dead(req: MarkDeadRequest):
    """Mark jobs as dead (removed, filled, broken link)."""
    job_ids = [normalize_job_id(jid) for jid in req.job_ids]
    updated_jobs = []
    not_found = []

    for job_id in job_ids:
        updated = data_update_job(job_id, {"dead": True})
        if updated:
            updated_jobs.append(job_id)
        else:
            not_found.append(job_id)

    if updated_jobs:
        broadcast_jobs_updated()

    return {"status": "ok", "updated": len(updated_jobs), "job_ids": updated_jobs, "not_found": not_found}


class ReorderJobsRequest(BaseModel):
    job_ids: list[str]  # Jobs in desired order


@router.post("/jobs/reorder")
def reorder_jobs(req: ReorderJobsRequest):
    """Set manual sort order for jobs."""
    job_ids = [normalize_job_id(jid) for jid in req.job_ids]
    results = get_results()
    jobs_by_id = {j.job_id: j for j in results.jobs}

    updated = []
    not_found = []

    for idx, job_id in enumerate(job_ids):
        if job_id not in jobs_by_id:
            not_found.append(job_id)
            continue
        job = data_update_job(job_id, {"sort_order": idx})
        if job:
            updated.append(job_id)

    if updated:
        broadcast_jobs_updated()

    return {
        "status": "ok",
        "reordered": len(updated),
        "job_ids": updated,
        "not_found": not_found,
    }


# --- View Control Routes ---


class SetViewRequest(BaseModel):
    view: str  # "select", "deep_dive", "application"


VIEW_MAP = {
    "select": 1,
    "deep_dive": 2,
    "deep_dives": 2,
    "application": 3,
    "applications": 3,
}


@router.post("/view")
def set_view(req: SetViewRequest):
    """Change the UI view (step)."""
    view = req.view.lower()
    if view not in VIEW_MAP:
        return {
            "status": "error",
            "error": f"Invalid view '{req.view}'. Use: select, deep_dive, application",
            "code": "INVALID_PARAM",
        }
    broadcast_view_changed(view)
    return {"status": "ok", "view": view, "step": VIEW_MAP[view]}
