"""
Job filtering based on user profile criteria.

Applies rules from:
- anti-positioning.md: What to avoid
- base.md: What to emphasize
"""

import re
from typing import Tuple

# Companies already disqualified or not relevant
BLOCKED_COMPANIES = {
    "bloomreach",      # Compensation mismatch (65% below minimum)
    "team.blue",       # Matrix coordination role
}

# Companies that are weak matches (not AI-focused, wrong sector, recruiters, etc.)
WEAK_COMPANIES = {
    "toptal",          # Generic PM roles, staff aug
    "relativity",      # E-discovery, not AI product
    "canonical",       # Ubuntu/Linux, not AI focus
    "voodoo",          # Mobile gaming
    "agileengine",     # Staff augmentation
    "cobbleweb",       # Marketplace agency
    "michael bailey",  # Recruiter posting
    "space executive", # Recruiter, low comp in title
    "iu international",# Education sector
    "voyage privé",    # Travel/leisure
    "hopper",          # Travel app
    "booksy",          # Beauty booking
    "eturnity",        # Energy SaaS
    "arise",           # German IT infrastructure
    "keyrock",         # Crypto, not AI agents
    "samsung food",    # Food app
    "tide",            # Banking, generic PM
    "wave mobile",     # Mobile payments Africa
    "cint",            # Market research, not AI
    "holafly",         # eSIM travel, not AI
}

# Title patterns that indicate leadership/management focus (avoid)
LEADERSHIP_PATTERNS = [
    r"\bhead of\b",
    r"\bdirector\b",
    r"\bvp\b",
    r"\bvice president\b",
    r"\bchief\b",
    r"\blead\s+of\b",  # "Lead of" but not "Lead PM"
    r"^lead\s+product",  # "Lead Product Manager" at start
]

# Title patterns indicating wrong level or focus (red flags)
RED_FLAG_PATTERNS = [
    r"\bgovernance\b",
    r"\badvisory\b",
    r"\bstrategic\s+alignment\b",
    r"\bstakeholder\s+alignment\b",
    r"\bprogram\s+manager\b",  # TPM/Program roles
    r"\bproject\s+manager\b",
    r"\bportfolio\b",
    r"\bjunior\b",  # Too junior
    r"\bassociate\b",  # Too junior
    r"\bintern\b",  # Too junior
]

# Positive signals (AI/ML relevance)
AI_SIGNALS = [
    r"\bai\b",
    r"\bartificial intelligence\b",
    r"\bml\b",
    r"\bmachine learning\b",
    r"\bllm\b",
    r"\blarge language\b",
    r"\bgenai\b",
    r"\bgenerative ai\b",
    r"\bagent\b",
    r"\bagentic\b",
    r"\bautomation\b",
    r"\bworkflow\b",
    r"\bdata\s+product\b",
    r"\bplatform\b",
]

# Strong positive signals (zero-to-one, shipping focus)
STRONG_SIGNALS = [
    r"\b0-1\b",
    r"\bzero.to.one\b",
    r"\bfounding\b",
    r"\bstaff\b",
    r"\bprincipal\b",
    r"\bsenior\b",
]


def _matches_any(text: str, patterns: list[str]) -> bool:
    """Check if text matches any pattern (case-insensitive)."""
    text_lower = text.lower()
    return any(re.search(p, text_lower) for p in patterns)


def _count_matches(text: str, patterns: list[str]) -> int:
    """Count how many patterns match (case-insensitive)."""
    text_lower = text.lower()
    return sum(1 for p in patterns if re.search(p, text_lower))


def filter_job(job: dict) -> Tuple[bool, str, int]:
    """
    Evaluate a job against user profile criteria.
    
    Args:
        job: Dict with title, company, location, job_url
        
    Returns:
        Tuple of (pass: bool, reason: str, relevance_score: int 0-10)
    """
    title = job.get("title", "")
    company = job.get("company", "")
    company_lower = company.lower().strip()
    
    # Hard blocks
    if any(blocked in company_lower for blocked in BLOCKED_COMPANIES):
        return False, f"Blocked company: {company}", 0
    
    # Weak companies (expanded list)
    if any(weak in company_lower for weak in WEAK_COMPANIES):
        return False, f"Weak company: {company}", 0
    
    if _matches_any(title, LEADERSHIP_PATTERNS):
        return False, "Leadership/director title", 0
    
    if _matches_any(title, RED_FLAG_PATTERNS):
        return False, "Red flag pattern in title", 0
    
    # Scoring
    score = 5  # Base score
    
    # AI relevance boost
    ai_matches = _count_matches(title, AI_SIGNALS)
    score += min(ai_matches * 2, 4)  # Up to +4 for AI signals
    
    # Strong signal boost
    if _matches_any(title, STRONG_SIGNALS):
        score += 1
    
    # Generic PM title penalty
    if re.search(r"^(senior\s+)?product\s+manager$", title.lower().strip()):
        score -= 2  # Generic title, no domain signal
    
    score = max(0, min(10, score))  # Clamp to 0-10
    
    if score >= 5:
        return True, "Passes criteria", score
    else:
        return False, "Low relevance score", score


def filter_jobs(jobs: list[dict]) -> Tuple[list[dict], list[dict]]:
    """
    Filter a list of jobs.
    
    Returns:
        Tuple of (passed_jobs, rejected_jobs)
        Each job gets 'filter_reason' and 'relevance_score' fields added.
    """
    passed = []
    rejected = []
    
    for job in jobs:
        passes, reason, score = filter_job(job)
        job["filter_reason"] = reason
        job["relevance_score"] = score
        
        if passes:
            passed.append(job)
        else:
            rejected.append(job)
    
    # Sort passed by relevance score descending
    passed.sort(key=lambda j: j["relevance_score"], reverse=True)
    
    # Deduplicate by title+company (keep highest score, which is first after sort)
    seen = set()
    deduped = []
    for job in passed:
        key = (job.get("title", "").strip().lower(), job.get("company", "").strip().lower())
        if key not in seen:
            seen.add(key)
            deduped.append(job)
        else:
            job["filter_reason"] = "Duplicate"
            rejected.append(job)
    
    return deduped, rejected
