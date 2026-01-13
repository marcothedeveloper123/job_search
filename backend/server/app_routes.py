"""API routes for application preparation - Step 3."""

from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from server.applications import (
    APPLICATIONS_DIR,
    FollowUp,
    GapAnalysis,
    InterviewPrep,
    JobSummary,
    ReferralSearch,
    SalaryResearch,
    archive_application,
    create_application,
    delete_application,
    export_document,
    get_application,
    list_applications,
    save_cover_letter,
    save_cv_tailored,
    save_follow_up,
    save_gap_analysis,
    save_interview_prep,
    save_jd,
    save_referral_search,
    save_salary_research,
    unarchive_application,
    update_application_status,
)
from server.data import get_jobs_by_ids
from server.utils import normalize_job_id
from server.websocket import broadcast_application_updated, broadcast_applications_changed, broadcast_view_changed

router = APIRouter(prefix="/api/applications")


# --- Slim Serializer (for Claude Desktop token efficiency) ---


def serialize_app_slim(app) -> dict:
    """Flat, minimal application representation for tool calls."""
    return {
        "app_id": app.application_id,
        "company": app.job.company if app.job else "",
        "title": app.job.title if app.job else "",
        "status": app.status,
        "has_cv": bool(app.cv_tailored),
        "has_cover": bool(app.cover_letter),
    }


# --- Request Models ---


class PrepareRequest(BaseModel):
    job_id: str


class UpdateJDRequest(BaseModel):
    jd: str


class UpdateGapAnalysisRequest(BaseModel):
    gap_analysis: GapAnalysis


class UpdateCVRequest(BaseModel):
    cv_tailored: str


class UpdateCoverRequest(BaseModel):
    cover_letter: str


class UpdatePrepRequest(BaseModel):
    interview_prep: InterviewPrep


class UpdateStatusRequest(BaseModel):
    status: str
    error: Optional[str] = None


# --- Routes ---


@router.post("/prepare")
def prepare_application(req: PrepareRequest):
    """
    Initiate application preparation for a job.

    Creates application directory, copies JD from job, returns application_id.
    Assumes job already has jd_text scraped.
    """
    job_id = normalize_job_id(req.job_id)
    # Get job from Step 1 data
    jobs = get_jobs_by_ids([job_id])
    if not jobs:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found")

    job = jobs[0]
    job_summary = JobSummary(
        job_id=job.job_id,
        title=job.title,
        company=job.company,
        url=job.url,
        location=job.location,
        posted=job.posted,
    )

    app = create_application(job_summary)

    # Copy JD from job (assumed to always exist)
    if job.jd_text:
        save_jd(app.application_id, job.jd_text)

    broadcast_application_updated(app.application_id)
    broadcast_view_changed("applications")
    return {
        "application_id": app.application_id,
        "status": app.status,
    }


@router.get("")
def get_applications(include_archived: bool = False, slim: bool = False):
    """List all application preps.

    Args:
        slim: If True, return flat minimal response for tool calls.
    """
    apps = list_applications(include_archived=include_archived)

    if slim:
        return {
            "status": "ok",
            "applications": [serialize_app_slim(a) for a in apps],
            "total": len(apps),
        }

    return {"applications": [a.model_dump() for a in apps]}


@router.get("/{application_id}")
def get_application_detail(application_id: str):
    """Get full application prep data."""
    app = get_application(application_id)
    if not app:
        raise HTTPException(status_code=404, detail="Application not found")
    return app.model_dump()


@router.delete("/{application_id}")
def remove_application(application_id: str):
    """Delete application prep and all files."""
    success = delete_application(application_id)
    if not success:
        raise HTTPException(status_code=404, detail="Application not found")
    broadcast_applications_changed()
    return {"status": "ok", "deleted": application_id}


class ArchiveApplicationsRequest(BaseModel):
    application_ids: list[str]


@router.post("/archive")
def archive_applications(req: ArchiveApplicationsRequest):
    """Archive applications."""
    archived = 0
    not_found = []
    for app_id in req.application_ids:
        success = archive_application(app_id)
        if success:
            archived += 1
        else:
            not_found.append(app_id)
    if archived > 0:
        broadcast_applications_changed()
    return {"status": "ok", "archived": archived, "not_found": not_found}


@router.post("/unarchive")
def unarchive_applications(req: ArchiveApplicationsRequest):
    """Unarchive applications."""
    unarchived = 0
    not_found = []
    for app_id in req.application_ids:
        success = unarchive_application(app_id)
        if success:
            unarchived += 1
        else:
            not_found.append(app_id)
    if unarchived > 0:
        broadcast_applications_changed()
    return {"status": "ok", "unarchived": unarchived, "not_found": not_found}


@router.put("/{application_id}/status")
def update_status(application_id: str, req: UpdateStatusRequest):
    """Update application status."""
    success = update_application_status(application_id, req.status, req.error)
    if not success:
        raise HTTPException(status_code=404, detail="Application not found")
    broadcast_application_updated(application_id)
    return {"status": "ok"}


@router.put("/{application_id}/jd")
def update_jd(application_id: str, req: UpdateJDRequest):
    """Save scraped job description."""
    success = save_jd(application_id, req.jd)
    if not success:
        raise HTTPException(status_code=404, detail="Application not found")
    broadcast_application_updated(application_id)
    return {"status": "ok"}


@router.put("/{application_id}/gap-analysis")
def update_gap_analysis(application_id: str, req: UpdateGapAnalysisRequest):
    """Save gap analysis."""
    success = save_gap_analysis(application_id, req.gap_analysis)
    if not success:
        raise HTTPException(status_code=404, detail="Application not found")
    broadcast_application_updated(application_id)
    return {"status": "ok"}


@router.put("/{application_id}/cv")
def update_cv(application_id: str, req: UpdateCVRequest):
    """Save tailored CV (versions previous if exists)."""
    success = save_cv_tailored(application_id, req.cv_tailored)
    if not success:
        raise HTTPException(status_code=404, detail="Application not found")
    broadcast_application_updated(application_id)
    return {"status": "ok"}


@router.put("/{application_id}/cover")
def update_cover(application_id: str, req: UpdateCoverRequest):
    """Save cover letter."""
    success = save_cover_letter(application_id, req.cover_letter)
    if not success:
        raise HTTPException(status_code=404, detail="Application not found")
    broadcast_application_updated(application_id)
    return {"status": "ok"}


@router.put("/{application_id}/interview-prep")
def update_interview_prep(application_id: str, req: UpdatePrepRequest):
    """Save interview prep notes."""
    success = save_interview_prep(application_id, req.interview_prep)
    if not success:
        raise HTTPException(status_code=404, detail="Application not found")
    broadcast_application_updated(application_id)
    return {"status": "ok"}


class UpdateSalaryRequest(BaseModel):
    salary_research: SalaryResearch


@router.put("/{application_id}/salary-research")
def update_salary_research(application_id: str, req: UpdateSalaryRequest):
    """Save salary research."""
    success = save_salary_research(application_id, req.salary_research)
    if not success:
        raise HTTPException(status_code=404, detail="Application not found")
    broadcast_application_updated(application_id)
    return {"status": "ok"}


class UpdateReferralRequest(BaseModel):
    referral_search: ReferralSearch


@router.put("/{application_id}/referral-search")
def update_referral_search(application_id: str, req: UpdateReferralRequest):
    """Save referral search results."""
    success = save_referral_search(application_id, req.referral_search)
    if not success:
        raise HTTPException(status_code=404, detail="Application not found")
    broadcast_application_updated(application_id)
    return {"status": "ok"}


class UpdateFollowUpRequest(BaseModel):
    follow_up: FollowUp


@router.put("/{application_id}/follow-up")
def update_follow_up(application_id: str, req: UpdateFollowUpRequest):
    """Save follow-up timeline."""
    success = save_follow_up(application_id, req.follow_up)
    if not success:
        raise HTTPException(status_code=404, detail="Application not found")
    broadcast_application_updated(application_id)
    return {"status": "ok"}


class ExportRequest(BaseModel):
    doc_type: str = "cv"  # "cv" or "cover"
    format: str = "docx"


@router.post("/{application_id}/export")
def export_application_doc(application_id: str, req: ExportRequest):
    """Export CV or cover letter to DOCX format."""
    result = export_document(application_id, req.doc_type, req.format)
    if result.get("status") == "error":
        raise HTTPException(status_code=400, detail=result.get("error"))
    return result


@router.get("/{application_id}/download/{filename}")
def download_file(application_id: str, filename: str):
    """Download exported file."""
    from fastapi.responses import FileResponse

    # Validate filename to prevent path traversal
    if "/" in filename or "\\" in filename or ".." in filename:
        raise HTTPException(status_code=400, detail="Invalid filename")

    file_path = APPLICATIONS_DIR / application_id / filename
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="File not found")

    return FileResponse(
        path=file_path,
        filename=filename,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    )
