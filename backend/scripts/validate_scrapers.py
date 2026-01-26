"""Scraper validation - health check for all job scrapers."""

from typing import Optional

REQUIRED_FIELDS = ["job_id", "title", "url", "source"]


def validate_job_structure(job: dict) -> list[str]:
    """Check if job has all required fields. Returns list of missing fields."""
    missing = []
    for field in REQUIRED_FIELDS:
        if not job.get(field):
            missing.append(field)
    return missing


def validate_linkedin() -> dict:
    """Validate LinkedIn scraper (auth required)."""
    from scripts.linkedin_auth import check_auth_status
    from scripts.linkedin_search import search_linkedin

    # Check auth first
    auth_result = check_auth_status()
    if auth_result.get("status") == "error":
        return {
            "scraper": "linkedin",
            "status": "fail",
            "reason": f"Auth check failed: {auth_result.get('error')}",
        }

    if not auth_result.get("authenticated"):
        return {
            "scraper": "linkedin",
            "status": "skip",
            "reason": "auth required",
            "auth": False,
        }

    # Run minimal search
    try:
        result = search_linkedin("product manager", max_pages=1)
    except Exception as e:
        return {
            "scraper": "linkedin",
            "status": "fail",
            "reason": str(e),
            "auth": True,
        }

    if result.get("status") != "ok":
        return {
            "scraper": "linkedin",
            "status": "fail",
            "reason": result.get("error", "Unknown error"),
            "auth": True,
        }

    jobs = result.get("jobs", [])
    if not jobs:
        return {
            "scraper": "linkedin",
            "status": "fail",
            "reason": "No jobs found",
            "auth": True,
        }

    # Validate job structure
    for job in jobs[:3]:
        missing = validate_job_structure(job)
        if missing:
            return {
                "scraper": "linkedin",
                "status": "fail",
                "reason": f"Missing fields: {', '.join(missing)}",
                "auth": True,
            }

    return {
        "scraper": "linkedin",
        "status": "pass",
        "job_count": len(jobs),
        "auth": True,
    }


def validate_jobscz() -> dict:
    """Validate jobs.cz scraper."""
    from scripts.jobscz_search import search_jobscz

    try:
        result = search_jobscz("product manager", max_pages=1)
    except Exception as e:
        return {"scraper": "jobscz", "status": "fail", "reason": str(e)}

    if result.get("status") != "ok":
        return {
            "scraper": "jobscz",
            "status": "fail",
            "reason": result.get("error", "Unknown error"),
        }

    jobs = result.get("jobs", [])
    if not jobs:
        return {"scraper": "jobscz", "status": "fail", "reason": "No jobs found"}

    for job in jobs[:3]:
        missing = validate_job_structure(job)
        if missing:
            return {
                "scraper": "jobscz",
                "status": "fail",
                "reason": f"Missing fields: {', '.join(missing)}",
            }

    return {"scraper": "jobscz", "status": "pass", "job_count": len(jobs)}


def validate_startupjobs() -> dict:
    """Validate startupjobs.cz scraper."""
    from scripts.startupjobs_search import search_startupjobs

    try:
        result = search_startupjobs("product manager", limit=10)
    except Exception as e:
        return {"scraper": "startupjobs", "status": "fail", "reason": str(e)}

    if result.get("status") != "ok":
        return {
            "scraper": "startupjobs",
            "status": "fail",
            "reason": result.get("error", "Unknown error"),
        }

    jobs = result.get("jobs", [])
    if not jobs:
        return {"scraper": "startupjobs", "status": "fail", "reason": "No jobs found"}

    for job in jobs[:3]:
        missing = validate_job_structure(job)
        if missing:
            return {
                "scraper": "startupjobs",
                "status": "fail",
                "reason": f"Missing fields: {', '.join(missing)}",
            }

    return {"scraper": "startupjobs", "status": "pass", "job_count": len(jobs)}


def validate_euremotejobs() -> dict:
    """Validate euremotejobs.com scraper."""
    from scripts.euremotejobs_search import search_euremotejobs

    try:
        result = search_euremotejobs("product manager", max_loads=1)
    except Exception as e:
        return {"scraper": "euremotejobs", "status": "fail", "reason": str(e)}

    if result.get("status") != "ok":
        return {
            "scraper": "euremotejobs",
            "status": "fail",
            "reason": result.get("error", "Unknown error"),
        }

    jobs = result.get("jobs", [])
    if not jobs:
        return {"scraper": "euremotejobs", "status": "fail", "reason": "No jobs found"}

    for job in jobs[:3]:
        missing = validate_job_structure(job)
        if missing:
            return {
                "scraper": "euremotejobs",
                "status": "fail",
                "reason": f"Missing fields: {', '.join(missing)}",
            }

    return {"scraper": "euremotejobs", "status": "pass", "job_count": len(jobs)}


SCRAPERS = [
    ("linkedin", validate_linkedin),
    ("jobscz", validate_jobscz),
    ("startupjobs", validate_startupjobs),
    ("euremotejobs", validate_euremotejobs),
]


def validate_all() -> dict:
    """Run validation on all scrapers."""
    results = []
    for name, validator in SCRAPERS:
        result = validator()
        results.append(result)

    passed = sum(1 for r in results if r["status"] == "pass")
    failed = sum(1 for r in results if r["status"] == "fail")
    skipped = sum(1 for r in results if r["status"] == "skip")

    return {
        "status": "ok" if failed == 0 else "partial",
        "passed": passed,
        "failed": failed,
        "skipped": skipped,
        "results": results,
    }


def format_human(summary: dict) -> str:
    """Format validation summary for human-readable output."""
    lines = ["Validating scrapers...", ""]

    for result in summary["results"]:
        name = result["scraper"].ljust(14)
        status = result["status"].upper()

        if status == "PASS":
            job_count = result.get("job_count", 0)
            auth = result.get("auth")
            auth_str = ", auth: yes" if auth else ""
            lines.append(f"{name} PASS  ({job_count} jobs{auth_str})")
        elif status == "SKIP":
            reason = result.get("reason", "")
            lines.append(f"{name} SKIP  ({reason})")
        else:
            reason = result.get("reason", "unknown error")
            lines.append(f"{name} FAIL  ({reason})")

    lines.append("")
    lines.append(f"Summary: {summary['passed']}/{len(summary['results'])} passed")

    if summary["skipped"] > 0:
        lines[-1] += f", {summary['skipped']} skipped"
    if summary["failed"] > 0:
        lines[-1] += f", {summary['failed']} failed"

    return "\n".join(lines)
