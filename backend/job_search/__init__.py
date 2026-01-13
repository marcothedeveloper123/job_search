"""Job Search UI Server API Client package."""

from job_search.http import URL as JOB_SEARCH_SERVER_URL
from job_search.tool import (
    # Status & Auth
    status,
    auth_status,
    login,
    # Search
    search_jobs,
    scrape_top_picks,
    # JD Scraping (auto-routes by job_id prefix)
    scrape_jd,
    scrape_jds,
    # Priority, Stage, Verdict
    set_priority,
    move_to_stage,
    set_verdict,
    # Archive & Order
    archive_jobs,
    unarchive_jobs,
    reorder_jobs,
    # Notes
    add_note,
    remove_note,
    get_notes,
    # Selections
    get_selections,
    select_jobs,
    deselect_jobs,
    # Jobs
    get_jobs,
    get_job,
    ingest_jobs,
    remove_jobs,
    update_job,
    # Deep Dives
    get_deep_dives,
    get_deep_dive,
    post_deep_dive,
    post_deep_dive_simple,
    update_deep_dive,
    delete_deep_dive,
    delete_deep_dives,
    archive_deep_dives,
    unarchive_deep_dives,
    # Applications
    prepare_application,
    get_applications,
    get_application,
    delete_application,
    archive_applications,
    unarchive_applications,
    update_application_jd,
    update_application_gap_analysis,
    update_application_cv,
    update_application_cover,
    update_application_interview_prep,
    update_application_status,
    # Company Knowledge
    get_prior_company_research,
    # View Control
    set_view,
)

__all__ = [
    # Status & Auth
    "status",
    "auth_status",
    "login",
    # Search
    "search_jobs",
    "scrape_top_picks",
    # JD Scraping
    "scrape_jd",
    "scrape_jds",
    # Priority, Stage, Verdict
    "set_priority",
    "move_to_stage",
    "set_verdict",
    # Archive & Order
    "archive_jobs",
    "unarchive_jobs",
    "reorder_jobs",
    # Notes
    "add_note",
    "remove_note",
    "get_notes",
    # Selections
    "get_selections",
    "select_jobs",
    "deselect_jobs",
    # Jobs
    "get_jobs",
    "get_job",
    "ingest_jobs",
    "remove_jobs",
    "update_job",
    # Deep Dives
    "get_deep_dives",
    "get_deep_dive",
    "post_deep_dive",
    "post_deep_dive_simple",
    "update_deep_dive",
    "delete_deep_dive",
    "delete_deep_dives",
    "archive_deep_dives",
    "unarchive_deep_dives",
    # Applications
    "prepare_application",
    "get_applications",
    "get_application",
    "delete_application",
    "archive_applications",
    "unarchive_applications",
    "update_application_jd",
    "update_application_gap_analysis",
    "update_application_cv",
    "update_application_cover",
    "update_application_interview_prep",
    "update_application_status",
    # Company Knowledge
    "get_prior_company_research",
    # View Control
    "set_view",
    # Config
    "JOB_SEARCH_SERVER_URL",
]
