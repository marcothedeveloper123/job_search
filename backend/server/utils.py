"""Shared utility functions for job processing."""

import hashlib
from datetime import datetime
from typing import Optional


def normalize_job_id(job_id: str) -> str:
    """Expand short IDs to full format: li_123 -> job_li_123, etc.

    Accepts both short (li_123) and full (job_li_123) formats.
    Returns full format for consistency.
    """
    if not job_id:
        return job_id
    if job_id.startswith("job_"):
        return job_id
    # Short prefixes for each source
    for prefix in ("li_", "er_", "cz_", "sj_"):
        if job_id.startswith(prefix):
            return "job_" + job_id
    # Bare numeric assumed to be LinkedIn
    if job_id.isdigit():
        return f"job_li_{job_id}"
    return job_id


def generate_job_id(url: str, title: str, company: str) -> str:
    """Generate stable job ID from content hash."""
    content = f"{url}:{title}:{company}"
    return f"job_{hashlib.md5(content.encode()).hexdigest()[:8]}"


def categorize_level(title: str) -> str:
    """Categorize job level from title."""
    t = title.lower()
    if "staff" in t:
        return "staff"
    if "principal" in t:
        return "principal"
    if "director" in t or "head of" in t or "vp " in t or "vice president" in t:
        return "leadership"
    if "senior" in t or "sr." in t or "sr " in t:
        return "senior"
    if "lead" in t:
        return "lead"
    return "other"


def has_ai_focus(title: str) -> bool:
    """Check if title suggests AI/ML focus."""
    keywords = ["ai", "ml", "machine learning", "llm", "genai", "generative", "gpt", "agent", "automation"]
    t = title.lower()
    return any(kw in t for kw in keywords)


def compute_days_ago(posted: Optional[str]) -> Optional[int]:
    """Compute days since job was posted from ISO date string."""
    if not posted:
        return None
    try:
        posted_date = datetime.fromisoformat(posted.replace("Z", "+00:00"))
        now = datetime.utcnow()
        if posted_date.tzinfo is not None:
            now = now.replace(tzinfo=posted_date.tzinfo)
        delta = now - posted_date
        return max(0, delta.days)
    except (ValueError, TypeError):
        return None


def level_rank(level: str) -> int:
    """Get numeric rank for level comparison."""
    ranks = {"other": 0, "senior": 1, "lead": 2, "staff": 3, "principal": 4, "leadership": 5}
    return ranks.get(level, 0)


# Staleness thresholds (days)
STALE_POSTED_DAYS = 45  # Job posted > 45 days ago
STALE_INGESTED_DAYS = 30  # Job ingested > 30 days ago (fallback)


def is_stale(posted: Optional[str], ingested_at: Optional[str]) -> bool:
    """
    Determine if a job is stale based on posting date or ingest time.

    - If posted date available: stale if > 45 days old
    - If only ingested_at available: stale if > 30 days old
    - If neither available: not stale (unknown)
    """
    # Prefer posted date (most accurate)
    if posted:
        days = compute_days_ago(posted)
        if days is not None:
            return days > STALE_POSTED_DAYS

    # Fall back to ingested_at
    if ingested_at:
        days = compute_days_ago(ingested_at)
        if days is not None:
            return days > STALE_INGESTED_DAYS

    # Unknown, assume not stale
    return False
