"""Data layer for job_search - JSON file read/write helpers.

For API documentation including data structures and field definitions,
see: references/api.md
"""

import hashlib
import json
from datetime import datetime
from pathlib import Path
from typing import Optional

from server.models import (
    Job, SearchParams, SearchResults,
    Selection, Selections,
    DeepDive, DeepDives,
    Research, Insights, Conclusions, Recommendations, ResearchNotes,
    Note, Notes,
)

# Re-export models for backward compatibility
__all__ = [
    # Models
    "Job", "SearchParams", "SearchResults", "ResearchNotes",
    "Selection", "Selections",
    "DeepDive", "DeepDives",
    "Research", "Insights", "Conclusions", "Recommendations",
    "Note", "Notes",
    # Constants
    "DATA_DIR", "RESULTS_FILE", "SELECTIONS_FILE", "DEEP_DIVES_FILE", "NOTES_FILE",
    # File operations
    "_read_json", "_write_json",
    # API functions
    "get_results", "save_results",
    "get_selections", "save_selections", "select_jobs", "deselect_jobs", "get_selections_by_source",
    "get_deep_dives", "get_deep_dive_by_id", "save_deep_dive", "remove_deep_dives",
    "delete_deep_dive", "archive_deep_dives", "unarchive_deep_dives",
    "get_jobs_by_ids", "remove_jobs", "update_job",
    "get_notes", "add_note", "remove_note",
    "JobNotFoundError",
    # Company knowledge
    "find_company_research", "normalize_company_name",
]

# Data directory at project root: /data/runtime/
DATA_DIR = Path(__file__).parent.parent.parent / "data" / "runtime"
DATA_DIR.mkdir(parents=True, exist_ok=True)

RESULTS_FILE = DATA_DIR / "results.json"
SELECTIONS_FILE = DATA_DIR / "selections.json"
DEEP_DIVES_FILE = DATA_DIR / "deep_dives.json"
NOTES_FILE = DATA_DIR / "notes.json"


class JobNotFoundError(Exception):
    """Raised when trying to save a deep dive for a non-existent job."""
    pass


# --- File Operations ---


def _read_json(path: Path, default: dict) -> dict:
    """Read JSON file, return default if not exists or invalid.

    Args:
        path: Path to JSON file
        default: Value to return if file missing or malformed
    """
    if not path.exists():
        return default
    try:
        data = json.loads(path.read_text())
        # Must be a dict, not a list
        if not isinstance(data, dict):
            return default
        return data
    except (json.JSONDecodeError, IOError):
        return default


def _write_json(path: Path, data: dict) -> None:
    """Write JSON file with pretty formatting."""
    path.write_text(json.dumps(data, indent=2))


# --- Results API ---


def get_results() -> SearchResults:
    """Get current search results."""
    data = _read_json(RESULTS_FILE, {"search_params": {"query": ""}, "jobs": []})
    return SearchResults.model_validate(data)


def save_results(results: SearchResults) -> None:
    """Save search results."""
    _write_json(RESULTS_FILE, results.model_dump())


# --- Selections API ---


def get_selections() -> Selections:
    """Get current selections, pruning any orphaned IDs."""
    data = _read_json(SELECTIONS_FILE, {"selections": [], "selected_ids": []})
    selections = Selections.model_validate(data)

    # Prune orphaned selections (IDs that no longer exist in job list)
    results = get_results()
    valid_ids = {job.job_id for job in results.jobs}

    # Prune new-style selections
    pruned_selections = [s for s in selections.selections if s.job_id in valid_ids]
    # Prune legacy selected_ids
    pruned_ids = [id for id in selections.selected_ids if id in valid_ids]

    if len(pruned_selections) != len(selections.selections) or len(pruned_ids) != len(selections.selected_ids):
        selections.selections = pruned_selections
        selections.selected_ids = pruned_ids
        save_selections(selections)

    return selections


def save_selections(selections: Selections) -> None:
    """Save selections."""
    _write_json(SELECTIONS_FILE, selections.model_dump())


def select_jobs(job_ids: list[str], source: str = "claude") -> dict:
    """Select jobs with source attribution.

    Args:
        job_ids: List of job IDs to select
        source: Attribution - "claude" or "user"

    Returns:
        {"status": "ok", "added": N, "not_found": [...]}
    """
    if source not in ("claude", "user"):
        return {"status": "error", "error": "Invalid source. Use: claude, user", "code": "INVALID_PARAM"}

    results = get_results()
    valid_ids = {job.job_id for job in results.jobs}

    selections = get_selections()
    existing_ids = {s.job_id for s in selections.selections}

    added = 0
    not_found = []

    for job_id in job_ids:
        if job_id not in valid_ids:
            not_found.append(job_id)
            continue
        if job_id not in existing_ids:
            selections.selections.append(Selection(job_id=job_id, source=source))
            # Also add to legacy field for backward compatibility
            if job_id not in selections.selected_ids:
                selections.selected_ids.append(job_id)
            existing_ids.add(job_id)
            added += 1

    selections.updated_at = datetime.utcnow().isoformat() + "Z"
    save_selections(selections)

    return {"status": "ok", "added": added, "not_found": not_found}


def deselect_jobs(job_ids: list[str]) -> dict:
    """Deselect jobs."""
    selections = get_selections()

    removed = 0
    for job_id in job_ids:
        original_len = len(selections.selections)
        selections.selections = [s for s in selections.selections if s.job_id != job_id]
        if len(selections.selections) < original_len:
            removed += 1
        # Also remove from legacy field
        if job_id in selections.selected_ids:
            selections.selected_ids.remove(job_id)

    selections.updated_at = datetime.utcnow().isoformat() + "Z"
    save_selections(selections)

    return {"status": "ok", "removed": removed}


def get_selections_by_source(source: Optional[str] = None) -> dict:
    """Get selections, optionally filtered by source."""
    selections = get_selections()

    if source is None:
        claude_ids = [s.job_id for s in selections.selections if s.source == "claude"]
        user_ids = [s.job_id for s in selections.selections if s.source == "user"]
        # Include legacy selected_ids as user selections for backward compatibility
        legacy_ids = [id for id in selections.selected_ids if id not in claude_ids and id not in user_ids]
        user_ids = user_ids + legacy_ids
        all_ids = claude_ids + user_ids
        return {"claude": claude_ids, "user": user_ids, "selected_ids": all_ids}
    elif source in ("claude", "user"):
        return [s.job_id for s in selections.selections if s.source == source]
    else:
        return {"status": "error", "error": "Invalid source", "code": "INVALID_PARAM"}


# --- Deep Dives API ---


def get_deep_dives() -> DeepDives:
    """Get all deep dives. Pure read - no side effects."""
    data = _read_json(DEEP_DIVES_FILE, {"deep_dives": []})
    return DeepDives.model_validate(data)


def get_deep_dive_by_id(job_id: str) -> Optional[DeepDive]:
    """Get a single deep dive by job ID."""
    dives = get_deep_dives()
    return next((d for d in dives.deep_dives if d.job_id == job_id), None)


def save_deep_dive(deep_dive: DeepDive) -> None:
    """Save or update a single deep dive. Validates job exists first."""
    # Validate job exists
    results = get_results()
    valid_ids = {job.job_id for job in results.jobs}
    if deep_dive.job_id not in valid_ids:
        raise JobNotFoundError(f"Job {deep_dive.job_id} not found in job list")

    dives = get_deep_dives()

    # Update existing or append new
    updated = False
    for i, d in enumerate(dives.deep_dives):
        if d.job_id == deep_dive.job_id:
            dives.deep_dives[i] = deep_dive
            updated = True
            break

    if not updated:
        dives.deep_dives.append(deep_dive)

    _write_json(DEEP_DIVES_FILE, dives.model_dump())


def remove_deep_dives(job_ids: list[str]) -> int:
    """Remove deep dives for given job IDs. Returns count removed."""
    dives = get_deep_dives()
    original_count = len(dives.deep_dives)
    dives.deep_dives = [d for d in dives.deep_dives if d.job_id not in job_ids]
    removed_count = original_count - len(dives.deep_dives)
    if removed_count > 0:
        _write_json(DEEP_DIVES_FILE, dives.model_dump())
    return removed_count


def delete_deep_dive(job_id: str) -> bool:
    """Delete a single deep dive by job ID. Returns True if found and deleted."""
    dives = get_deep_dives()
    original_count = len(dives.deep_dives)
    dives.deep_dives = [d for d in dives.deep_dives if d.job_id != job_id]
    if len(dives.deep_dives) < original_count:
        _write_json(DEEP_DIVES_FILE, dives.model_dump())
        return True
    return False


def archive_deep_dives(job_ids: list[str]) -> tuple[int, list[str]]:
    """Archive deep dives by job IDs. Returns (archived_count, not_found_ids)."""
    dives = get_deep_dives()
    archived = 0
    found_ids = set()
    for d in dives.deep_dives:
        if d.job_id in job_ids and not d.archived:
            d.archived = True
            d.updated_at = datetime.utcnow().isoformat() + "Z"
            archived += 1
            found_ids.add(d.job_id)
    not_found = [jid for jid in job_ids if jid not in found_ids]
    if archived > 0:
        _write_json(DEEP_DIVES_FILE, dives.model_dump())
    return archived, not_found


def unarchive_deep_dives(job_ids: list[str]) -> tuple[int, list[str]]:
    """Unarchive deep dives by job IDs. Returns (unarchived_count, not_found_ids)."""
    dives = get_deep_dives()
    unarchived = 0
    found_ids = set()
    for d in dives.deep_dives:
        if d.job_id in job_ids and d.archived:
            d.archived = False
            d.updated_at = datetime.utcnow().isoformat() + "Z"
            unarchived += 1
            found_ids.add(d.job_id)
    not_found = [jid for jid in job_ids if jid not in found_ids]
    if unarchived > 0:
        _write_json(DEEP_DIVES_FILE, dives.model_dump())
    return unarchived, not_found


# --- Jobs API ---


def get_jobs_by_ids(ids: list[str]) -> list[Job]:
    """Get jobs by their IDs."""
    results = get_results()
    return [j for j in results.jobs if j.job_id in ids]


def remove_jobs(ids: list[str]) -> tuple[int, list[str]]:
    """Remove jobs by their IDs. Returns (removed_count, not_found_ids)."""
    results = get_results()
    existing_ids = {j.job_id for j in results.jobs}
    not_found = [i for i in ids if i not in existing_ids]

    results.jobs = [j for j in results.jobs if j.job_id not in ids]
    removed_count = len(ids) - len(not_found)

    if removed_count > 0:
        _write_json(RESULTS_FILE, results.model_dump())
    return removed_count, not_found


def update_job(job_id: str, updates: dict) -> Optional[Job]:
    """Update a job by ID with provided fields.

    Args:
        job_id: ID of job to update
        updates: Dict of field names to new values (see Job model for fields)

    Returns:
        Updated Job model, or None if job_id not found
    """
    results = get_results()

    # Find and update the job
    for i, job in enumerate(results.jobs):
        if job.job_id == job_id:
            # Merge updates into existing job data
            job_data = job.model_dump()
            # Only update fields that exist in Job model and are provided
            valid_fields = set(Job.model_fields.keys())
            for key, value in updates.items():
                if key in valid_fields and key != "job_id":  # Never allow ID change
                    job_data[key] = value

            updated_job = Job.model_validate(job_data)
            results.jobs[i] = updated_job
            _write_json(RESULTS_FILE, results.model_dump())
            return updated_job

    return None


# --- Notes API ---


def get_notes(job_id: Optional[str] = None) -> list[Note]:
    """Get notes, optionally filtered by job_id."""
    data = _read_json(NOTES_FILE, {"notes": []})
    notes_data = Notes.model_validate(data)
    if job_id:
        return [n for n in notes_data.notes if n.job_id == job_id]
    return notes_data.notes


def add_note(job_id: str, text: str) -> Note:
    """Add a note for a job.

    Args:
        job_id: ID of job to attach note to
        text: Note content (truncated to 500 chars)

    Returns:
        Created Note model

    Raises:
        JobNotFoundError: If job_id doesn't exist
    """
    timestamp = datetime.utcnow().isoformat()
    note_id = f"note_{hashlib.md5(f'{job_id}:{timestamp}'.encode()).hexdigest()[:8]}"

    # Validate job exists
    results = get_results()
    valid_ids = {job.job_id for job in results.jobs}
    if job_id not in valid_ids:
        raise JobNotFoundError(f"Job {job_id} not found")

    # Truncate text to 500 chars
    text = text[:500]

    note = Note(note_id=note_id, job_id=job_id, text=text, created_at=timestamp + "Z")

    data = _read_json(NOTES_FILE, {"notes": []})
    notes_data = Notes.model_validate(data)
    notes_data.notes.append(note)
    _write_json(NOTES_FILE, notes_data.model_dump())

    return note


def remove_note(note_id: str) -> bool:
    """Remove a note by ID. Returns True if removed, False if not found."""
    data = _read_json(NOTES_FILE, {"notes": []})
    notes_data = Notes.model_validate(data)

    original_count = len(notes_data.notes)
    notes_data.notes = [n for n in notes_data.notes if n.note_id != note_id]

    if len(notes_data.notes) < original_count:
        _write_json(NOTES_FILE, notes_data.model_dump())
        return True
    return False


# --- Company Knowledge API ---


def normalize_company_name(name: str) -> str:
    """Normalize company name for matching."""
    name = name.lower().strip()
    # Strip common suffixes
    for suffix in [" inc", " inc.", " llc", " ltd", " ltd.", ".com", ".io", ".ai"]:
        if name.endswith(suffix):
            name = name[:-len(suffix)]
    return name.strip()


def find_company_research(company_name: str) -> dict:
    """
    Search deep dives for matching company, return aggregated research.
    Uses fuzzy matching on company name.
    """
    normalized_query = normalize_company_name(company_name)
    if not normalized_query:
        return {"found": False}

    # Get all jobs to map job_id -> company
    results = get_results()
    job_company_map = {job.job_id: job.company for job in results.jobs}

    # Get all deep dives and find matches
    dives = get_deep_dives()
    matches = []

    for dd in dives.deep_dives:
        company = job_company_map.get(dd.job_id, "")
        if not company:
            continue
        normalized_company = normalize_company_name(company)
        # Match if query equals company or is contained in it (or vice versa)
        if normalized_query == normalized_company or normalized_query in normalized_company or normalized_company in normalized_query:
            matches.append((dd, company))

    if not matches:
        return {"found": False}

    # Score matches by completeness and recency
    def research_score(dd: DeepDive) -> tuple:
        score = 0
        # Has research_notes (most valuable)
        if dd.research_notes:
            notes = dd.research_notes
            score += len(notes.employee) + len(notes.customer) + len(notes.company)
        # Has legacy research
        if dd.research:
            r = dd.research
            if r.company:
                score += sum(1 for v in [r.company.size, r.company.funding, r.company.stage, r.company.product, r.company.market] if v)
        return (score, dd.updated_at or "")

    # Get the most complete deep dive
    best_dd, best_company = max(matches, key=lambda x: research_score(x[0]))

    # Build summary
    summary_parts = []
    if best_dd.research and best_dd.research.company:
        c = best_dd.research.company
        if c.stage:
            summary_parts.append(f"Stage: {c.stage[:100]}")
        if c.product:
            summary_parts.append(f"Product: {c.product[:100]}")
    if best_dd.conclusions:
        if best_dd.conclusions.concerns:
            summary_parts.append(f"Concerns: {'; '.join(best_dd.conclusions.concerns[:3])}")
        if best_dd.conclusions.fit_score is not None:
            summary_parts.append(f"Prior fit score: {best_dd.conclusions.fit_score}/10")

    return {
        "found": True,
        "company_name": best_company,
        "research_notes": best_dd.research_notes.model_dump() if best_dd.research_notes else None,
        "research": best_dd.research.model_dump() if best_dd.research else None,
        "summary": " | ".join(summary_parts) if summary_parts else None,
        "source_job_ids": [m[0].job_id for m in matches],
        "last_updated": best_dd.updated_at,
    }
