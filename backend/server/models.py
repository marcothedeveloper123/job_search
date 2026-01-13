"""Pydantic models for job_search data structures."""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field, field_validator


# --- Job Models ---


class Job(BaseModel):
    job_id: str
    title: str
    company: str
    location: Optional[str] = None
    salary: Optional[str] = None
    url: str
    source: str
    level: Optional[str] = None
    ai_focus: bool = False
    posted: Optional[str] = None
    days_ago: Optional[int] = None
    ingested_at: Optional[str] = None  # When job was first added to board
    # Workflow fields
    priority: Optional[str] = None  # "high", "medium", "low", None
    stage: Optional[str] = None  # "select", "deep_dive", "application", None
    verdict: Optional[str] = None  # "Pursue", "Maybe", "Skip", None
    archived: bool = False
    dead: bool = False  # Listing no longer available (removed, filled, broken link)
    sort_order: Optional[int] = None  # Manual ordering (lower = higher in list)
    # JD scraping
    jd_text: Optional[str] = None
    jd_scraped_at: Optional[str] = None


class SearchParams(BaseModel):
    query: str
    location: Optional[str] = None
    days: Optional[int] = None
    sites: list[str] = Field(default_factory=lambda: ["indeed"])
    n: int = 10
    remote: Optional[bool] = None
    timestamp: str = Field(default_factory=lambda: datetime.utcnow().isoformat() + "Z")


class SearchResults(BaseModel):
    search_params: SearchParams
    jobs: list[Job] = Field(default_factory=list)


# --- Selection Models ---


class Selection(BaseModel):
    job_id: str
    source: str  # "claude" or "user"


class Selections(BaseModel):
    selections: list[Selection] = Field(default_factory=list)
    # Legacy field for backward compatibility
    selected_ids: list[str] = Field(default_factory=list)
    updated_at: str = Field(default_factory=lambda: datetime.utcnow().isoformat() + "Z")


# --- Research Models ---


class ResearchItem(BaseModel):
    """A factual finding with source link and sentiment."""
    finding: str  # The fact with markdown link
    sentiment: str = "neutral"  # "positive" | "negative" | "neutral"


class CompanyResearch(BaseModel):
    size: Optional[str] = None
    funding: Optional[str] = None
    stage: Optional[str] = None
    product: Optional[str] = None
    market: Optional[str] = None


class RoleResearch(BaseModel):
    scope: Optional[str] = None
    team: Optional[str] = None
    tech_stack: Optional[str] = None


class SentimentResearch(BaseModel):
    """Employee and customer sentiment with itemized findings."""
    employee: list[ResearchItem] = Field(default_factory=list)  # Glassdoor, Blind
    customer: list[ResearchItem] = Field(default_factory=list)  # G2, TrustRadius, Reddit

    @field_validator("employee", "customer", mode="before")
    @classmethod
    def coerce_none_to_list(cls, v):
        """Handle legacy None values and plain strings."""
        if v is None:
            return []
        if isinstance(v, str):
            return []  # Can't convert plain string to itemized format
        return v


class ContextResearch(BaseModel):
    """Market context, interview process, and remote reality findings."""
    market: list[ResearchItem] = Field(default_factory=list)  # Competitors, news
    interview_process: list[ResearchItem] = Field(default_factory=list)  # Glassdoor interviews
    remote_reality: list[ResearchItem] = Field(default_factory=list)  # Actual remote policy

    @field_validator("market", "interview_process", "remote_reality", mode="before")
    @classmethod
    def coerce_none_to_list(cls, v):
        """Handle legacy None values and plain strings."""
        if v is None:
            return []
        if isinstance(v, str):
            return []  # Can't convert plain string to itemized format
        return v


class CompensationResearch(BaseModel):
    found: bool = False
    estimate: Optional[str] = None
    notes: Optional[str] = None


class Research(BaseModel):
    company: CompanyResearch = Field(default_factory=CompanyResearch)
    role: RoleResearch = Field(default_factory=RoleResearch)
    sentiment: SentimentResearch = Field(default_factory=SentimentResearch)
    context: ContextResearch = Field(default_factory=ContextResearch)
    compensation: CompensationResearch = Field(default_factory=CompensationResearch)


class ResearchNotes(BaseModel):
    """Structured research findings categorized by source type."""
    employee: list[ResearchItem] = Field(default_factory=list)  # Glassdoor, Blind, LinkedIn
    customer: list[ResearchItem] = Field(default_factory=list)  # Reddit, G2, Trustpilot
    company: list[ResearchItem] = Field(default_factory=list)   # Crunchbase, news, funding

    @field_validator("employee", "customer", "company", mode="before")
    @classmethod
    def coerce_none_to_list(cls, v):
        """Handle legacy None values."""
        if v is None:
            return []
        return v


# --- Job Description and Enhanced Insights ---


class JobDescription(BaseModel):
    """Scraped job description with metadata."""
    raw_text: str
    scraped_at: str  # ISO timestamp
    source_url: str
    scrape_status: str = "complete"  # "complete" | "partial" | "failed" | "manual"


class AlignmentItem(BaseModel):
    """A JD requirement with matching evidence from profile."""
    requirement: str
    evidence: str
    strength: str  # "strong" | "partial" | "weak"


class ConcernItem(BaseModel):
    """A JD requirement where there's a gap."""
    requirement: str
    gap: str
    mitigation: Optional[str] = None


class MissingRequirement(BaseModel):
    """A JD requirement that cannot be met."""
    requirement: str
    assessment: str


class EnhancedInsights(BaseModel):
    """Evidence-based insights derived from JD analysis."""
    alignment: list[AlignmentItem] = Field(default_factory=list)
    concerns: list[ConcernItem] = Field(default_factory=list)
    missing_requirements: list[MissingRequirement] = Field(default_factory=list)


# Legacy insights model for backward compatibility
class Insights(BaseModel):
    comparison: Optional[str] = None
    posting_analysis: Optional[str] = None
    market_context: Optional[str] = None


# --- Conclusions and Recommendations ---


class DealbreakersCheck(BaseModel):
    matrix_coordination: bool = False
    leadership_disguised: bool = False
    advisory_role: bool = False


class Conclusions(BaseModel):
    fit_score: Optional[int] = None
    fit_explanation: Optional[str] = None
    concerns: list[str] = Field(default_factory=list)
    attractions: list[str] = Field(default_factory=list)
    dealbreaker_check: DealbreakersCheck = Field(default_factory=DealbreakersCheck)


class Recommendations(BaseModel):
    verdict: Optional[str] = None  # "Pursue", "Maybe", "Skip"
    questions_to_ask: list[str] = Field(default_factory=list)
    next_steps: list[str] = Field(default_factory=list)


# --- Deep Dive Models ---


class DeepDive(BaseModel):
    job_id: str
    status: str = "pending"  # "pending", "complete"
    archived: bool = False
    updated_at: str = Field(default_factory=lambda: datetime.utcnow().isoformat() + "Z")
    research: Research = Field(default_factory=Research)
    research_notes: Optional[ResearchNotes] = None  # Structured findings with sources
    jd: Optional[JobDescription] = None  # Scraped job description
    insights: Insights = Field(default_factory=Insights)  # Legacy insights
    enhanced_insights: Optional[EnhancedInsights] = None  # Evidence-based insights from JD
    conclusions: Conclusions = Field(default_factory=Conclusions)
    recommendations: Recommendations = Field(default_factory=Recommendations)


class DeepDives(BaseModel):
    deep_dives: list[DeepDive] = Field(default_factory=list)


# --- Note Models ---


class Note(BaseModel):
    note_id: str
    job_id: str
    text: str
    created_at: str = Field(default_factory=lambda: datetime.utcnow().isoformat() + "Z")


class Notes(BaseModel):
    notes: list[Note] = Field(default_factory=list)
