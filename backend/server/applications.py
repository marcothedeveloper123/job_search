"""Data layer for application preparation - Step 3."""

import json
import re
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from pydantic import BaseModel, Field

from server.docx_export import markdown_to_docx


APPLICATIONS_DIR = Path(__file__).parent.parent / "applications"
APPLICATIONS_DIR.mkdir(exist_ok=True)


# --- Pydantic Models ---


class GapAnalysis(BaseModel):
    """Gap analysis matching JD requirements to user profile."""
    matches: list[str] = Field(default_factory=list)
    partial_matches: list[str] = Field(default_factory=list)
    gaps: list[str] = Field(default_factory=list)
    missing_stories: list[str] = Field(default_factory=list)


class WhatToSayItem(BaseModel):
    """Interview response preparation."""
    question: str
    answer: str


class InterviewPrep(BaseModel):
    """Interview preparation with responses and warnings."""
    what_to_say: list[WhatToSayItem] = Field(default_factory=list)
    what_not_to_say: list[str] = Field(default_factory=list)
    questions_to_ask: list[str] = Field(default_factory=list)
    red_flags: list[str] = Field(default_factory=list)


class SalaryResearch(BaseModel):
    """Salary intelligence for negotiation."""
    range: Optional[str] = None
    glassdoor: Optional[str] = None
    levels_fyi: Optional[str] = None
    blind: Optional[str] = None
    anchoring_strategy: Optional[str] = None


class ReferralSearch(BaseModel):
    """Referral hunting results."""
    contacts: list[str] = Field(default_factory=list)
    channel_priority: list[str] = Field(default_factory=list)


class FollowUp(BaseModel):
    """Follow-up timeline and backup contacts."""
    milestones: list[str] = Field(default_factory=list)
    backup_contacts: list[str] = Field(default_factory=list)


class JobSummary(BaseModel):
    job_id: str
    title: str
    company: str
    url: str
    location: Optional[str] = None
    posted: Optional[str] = None


class ApplicationMetadata(BaseModel):
    application_id: str
    job: JobSummary
    status: str = "pending"  # pending, scraping, generating, complete, error
    error: Optional[str] = None
    archived: bool = False
    created_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    updated_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    versions: list[str] = Field(default_factory=list)


class Application(BaseModel):
    application_id: str
    status: str = "pending"
    job: JobSummary
    jd: Optional[str] = None
    gap_analysis: Optional[GapAnalysis] = None
    cv_tailored: Optional[str] = None
    cover_letter: Optional[str] = None
    interview_prep: Optional[InterviewPrep] = None
    salary_research: Optional[SalaryResearch] = None
    referral_search: Optional[ReferralSearch] = None
    follow_up: Optional[FollowUp] = None
    created_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    updated_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )


class ApplicationSummary(BaseModel):
    application_id: str
    job_id: str
    job_title: str
    company: str
    status: str
    archived: bool = False
    created_at: str


# --- Helper Functions ---


def _slugify(text: str) -> str:
    """Convert text to URL-safe slug."""
    text = text.lower().strip()
    text = re.sub(r"[^\w\s-]", "", text)
    text = re.sub(r"[\s_]+", "-", text)
    text = re.sub(r"-+", "-", text)
    return text[:50].strip("-")


def _generate_application_id(company: str, title: str) -> str:
    """Generate application ID: YYYY-MM-DD-company-slug-title-slug."""
    date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    company_slug = _slugify(company)
    title_slug = _slugify(title)
    return f"{date}-{company_slug}-{title_slug}"


def _get_app_dir(application_id: str) -> Path:
    """Get directory path for an application."""
    return APPLICATIONS_DIR / application_id


# --- Storage Functions ---


def create_application(job: JobSummary) -> Application:
    """Create a new application prep directory and metadata."""
    application_id = _generate_application_id(job.company, job.title)
    app_dir = _get_app_dir(application_id)

    # Handle duplicate IDs by appending counter
    counter = 1
    original_id = application_id
    while app_dir.exists():
        application_id = f"{original_id}-{counter}"
        app_dir = _get_app_dir(application_id)
        counter += 1

    app_dir.mkdir(parents=True, exist_ok=True)

    # Create metadata
    metadata = ApplicationMetadata(
        application_id=application_id,
        job=job,
        status="pending",
    )
    _save_metadata(application_id, metadata)

    return Application(
        application_id=application_id,
        status="pending",
        job=job,
    )


def get_application(application_id: str) -> Optional[Application]:
    """Load full application data from disk."""
    app_dir = _get_app_dir(application_id)
    if not app_dir.exists():
        return None

    metadata = _load_metadata(application_id)
    if not metadata:
        return None

    # Load optional files
    jd = _read_file(app_dir / "jd.md")
    gap_analysis = _read_json(app_dir / "gap-analysis.json")
    cv_tailored = _read_file(app_dir / "cv-tailored.md")
    cover_letter = _read_file(app_dir / "cover.md")
    prep_notes = _read_json(app_dir / "prep-notes.json")
    salary_research = _read_json(app_dir / "salary-research.json")
    referral_search = _read_json(app_dir / "referral-search.json")
    follow_up = _read_json(app_dir / "follow-up.json")

    return Application(
        application_id=application_id,
        status=metadata.status,
        job=metadata.job,
        jd=jd,
        gap_analysis=GapAnalysis.model_validate(gap_analysis) if gap_analysis else None,
        cv_tailored=cv_tailored,
        cover_letter=cover_letter,
        interview_prep=InterviewPrep.model_validate(prep_notes) if prep_notes else None,
        salary_research=SalaryResearch.model_validate(salary_research) if salary_research else None,
        referral_search=ReferralSearch.model_validate(referral_search) if referral_search else None,
        follow_up=FollowUp.model_validate(follow_up) if follow_up else None,
        created_at=metadata.created_at,
        updated_at=metadata.updated_at,
    )


def list_applications(include_archived: bool = False) -> list[ApplicationSummary]:
    """List all applications with summary info."""
    applications = []
    for app_dir in sorted(APPLICATIONS_DIR.iterdir(), reverse=True):
        if not app_dir.is_dir():
            continue
        metadata = _load_metadata(app_dir.name)
        if metadata:
            if not include_archived and metadata.archived:
                continue
            applications.append(ApplicationSummary(
                application_id=metadata.application_id,
                job_id=metadata.job.job_id,
                job_title=metadata.job.title,
                company=metadata.job.company,
                status=metadata.status,
                archived=metadata.archived,
                created_at=metadata.created_at,
            ))
    return applications


def delete_application(application_id: str) -> bool:
    """Delete application and all associated files."""
    app_dir = _get_app_dir(application_id)
    if not app_dir.exists():
        return False
    shutil.rmtree(app_dir)
    return True


def archive_application(application_id: str) -> bool:
    """Archive an application."""
    metadata = _load_metadata(application_id)
    if not metadata:
        return False
    metadata.archived = True
    metadata.updated_at = datetime.now(timezone.utc).isoformat()
    _save_metadata(application_id, metadata)
    return True


def unarchive_application(application_id: str) -> bool:
    """Unarchive an application."""
    metadata = _load_metadata(application_id)
    if not metadata:
        return False
    metadata.archived = False
    metadata.updated_at = datetime.now(timezone.utc).isoformat()
    _save_metadata(application_id, metadata)
    return True


def update_application_status(application_id: str, status: str, error: str | None = None) -> bool:
    """Update application status."""
    metadata = _load_metadata(application_id)
    if not metadata:
        return False
    metadata.status = status
    metadata.error = error
    metadata.updated_at = datetime.now(timezone.utc).isoformat()
    _save_metadata(application_id, metadata)
    return True


def save_jd(application_id: str, jd_content: str) -> bool:
    """Save scraped job description."""
    app_dir = _get_app_dir(application_id)
    if not app_dir.exists():
        return False
    (app_dir / "jd.md").write_text(jd_content)
    return True


def save_gap_analysis(application_id: str, gap_analysis: GapAnalysis) -> bool:
    """Save gap analysis."""
    app_dir = _get_app_dir(application_id)
    if not app_dir.exists():
        return False
    _write_json(app_dir / "gap-analysis.json", gap_analysis.model_dump())
    return True


def save_cv_tailored(application_id: str, content: str) -> bool:
    """Save tailored CV, versioning previous if exists. Auto-generates DOCX."""
    app_dir = _get_app_dir(application_id)
    if not app_dir.exists():
        return False

    cv_path = app_dir / "cv-tailored.md"
    if cv_path.exists():
        _version_file(application_id, cv_path)
    cv_path.write_text(content)

    # Auto-generate DOCX
    try:
        markdown_to_docx(content, app_dir / "cv.docx")
    except Exception:
        pass  # DOCX generation is best-effort, don't fail the save

    return True


def save_cover_letter(application_id: str, content: str) -> bool:
    """Save cover letter. Auto-generates DOCX."""
    app_dir = _get_app_dir(application_id)
    if not app_dir.exists():
        return False
    (app_dir / "cover.md").write_text(content)

    # Auto-generate DOCX
    try:
        markdown_to_docx(content, app_dir / "cover.docx")
    except Exception:
        pass  # DOCX generation is best-effort, don't fail the save

    return True


def save_interview_prep(application_id: str, prep: InterviewPrep) -> bool:
    """Save interview prep notes."""
    app_dir = _get_app_dir(application_id)
    if not app_dir.exists():
        return False
    _write_json(app_dir / "prep-notes.json", prep.model_dump())
    return True


def save_salary_research(application_id: str, research: SalaryResearch) -> bool:
    """Save salary research."""
    app_dir = _get_app_dir(application_id)
    if not app_dir.exists():
        return False
    _write_json(app_dir / "salary-research.json", research.model_dump())
    return True


def save_referral_search(application_id: str, search: ReferralSearch) -> bool:
    """Save referral search results."""
    app_dir = _get_app_dir(application_id)
    if not app_dir.exists():
        return False
    _write_json(app_dir / "referral-search.json", search.model_dump())
    return True


def save_follow_up(application_id: str, follow_up: FollowUp) -> bool:
    """Save follow-up timeline."""
    app_dir = _get_app_dir(application_id)
    if not app_dir.exists():
        return False
    _write_json(app_dir / "follow-up.json", follow_up.model_dump())
    return True


# --- File Helpers ---


def _load_metadata(application_id: str) -> Optional[ApplicationMetadata]:
    """Load application metadata."""
    path = _get_app_dir(application_id) / "metadata.json"
    data = _read_json(path)
    if data:
        return ApplicationMetadata.model_validate(data)
    return None


def _save_metadata(application_id: str, metadata: ApplicationMetadata) -> None:
    """Save application metadata."""
    path = _get_app_dir(application_id) / "metadata.json"
    _write_json(path, metadata.model_dump())


def _read_file(path: Path) -> Optional[str]:
    """Read text file, return None if not exists."""
    if path.exists():
        return path.read_text()
    return None


def _read_json(path: Path) -> Optional[dict]:
    """Read JSON file, return None if not exists or invalid."""
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text())
    except (json.JSONDecodeError, IOError):
        return None


def _write_json(path: Path, data: dict) -> None:
    """Write JSON file with pretty formatting."""
    path.write_text(json.dumps(data, indent=2))


def _version_file(application_id: str, path: Path) -> None:
    """Create versioned backup of file."""
    metadata = _load_metadata(application_id)
    if not metadata:
        return

    # Find next version number
    stem = path.stem
    suffix = path.suffix
    version = 1
    while (path.parent / f"{stem}.v{version}{suffix}").exists():
        version += 1

    # Move current to versioned
    versioned_path = path.parent / f"{stem}.v{version}{suffix}"
    path.rename(versioned_path)

    # Track version
    metadata.versions.append(versioned_path.name)
    metadata.updated_at = datetime.now(timezone.utc).isoformat()
    _save_metadata(application_id, metadata)


# --- Export Functions ---


def export_document(
    application_id: str,
    doc_type: str = "cv",
    format: str = "docx",
) -> Optional[dict]:
    """
    Export application document (CV or cover letter) to DOCX format.

    Args:
        application_id: The application ID
        doc_type: "cv" or "cover"
        format: "docx" (only supported format currently)

    Returns:
        {"status": "ok", "path": "...", "filename": "..."} or None if failed
    """
    if format != "docx":
        return {"status": "error", "error": f"Unsupported format: {format}"}

    if doc_type not in ("cv", "cover"):
        return {"status": "error", "error": f"Invalid doc_type: {doc_type}"}

    app_dir = _get_app_dir(application_id)
    if not app_dir.exists():
        return {"status": "error", "error": "Application not found"}

    # Read source markdown
    source_file = "cv-tailored.md" if doc_type == "cv" else "cover.md"
    markdown_content = _read_file(app_dir / source_file)
    if not markdown_content:
        return {"status": "error", "error": f"No {doc_type} content to export"}

    # Convert to DOCX
    output_filename = f"{doc_type}.docx"
    output_path = app_dir / output_filename

    try:
        markdown_to_docx(markdown_content, output_path)
    except Exception as e:
        return {"status": "error", "error": f"Export failed: {str(e)}"}

    return {
        "status": "ok",
        "path": str(output_path),
        "filename": output_filename,
    }
