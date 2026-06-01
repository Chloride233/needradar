from __future__ import annotations

import datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field

from needradar.models.crawl_task import TaskStatus
from needradar.models.link import LinkType
from needradar.models.scheduled_job import JobStatus
from needradar.schemas.mixins import HasKeyword, HasSentiment, HasSource

# --- Enums ---

class PlatformEnum(str, Enum):
    GITHUB = "github"
    STACKOVERFLOW = "stackoverflow"
    JUEJIN = "juejin"
    BILIBILI = "bilibili"
    ZHIHU = "zhihu"
    CSDN = "csdn"
    TIEBA = "tieba"
    DOUBAN = "douban"
    XIAOHONGSHU = "xiaohongshu"


class SentimentEnum(str, Enum):
    STRONG = "strong"
    MODERATE = "moderate"
    MILD = "mild"


class EmotionEnum(str, Enum):
    POSITIVE = "positive"
    NEGATIVE = "negative"
    NEUTRAL = "neutral"


# --- Task Schemas ---

class TaskCreateRequest(BaseModel):
    keyword: str = Field(..., min_length=1, max_length=200)
    platforms: list[PlatformEnum] = Field(default_factory=lambda: list(PlatformEnum))


class TaskResponse(BaseModel):
    id: int
    keyword: str
    platform: str
    status: TaskStatus
    total_items: int
    new_items: int = 0
    skipped_items: int = 0
    noise_count: int = 0
    extracted_count: int = 0
    filter_mode: str = "off"
    error_message: str | None
    report_path: str | None = None
    created_at: datetime.datetime
    updated_at: datetime.datetime | None = None

    model_config = ConfigDict(from_attributes=True)


class TaskListResponse(BaseModel):
    items: list[TaskResponse]
    total: int


# --- Requirement Schemas (from vault frontmatter) ---

class RequirementResponse(BaseModel, HasSource, HasSentiment, HasKeyword):
    title: str
    description: str = ""
    source_platform: str = ""
    source_url: str = ""
    sentiment: str = "moderate"
    emotion: str = "neutral"
    confidence: float = 0.0
    mention_count: int = 1
    keyword: str = ""
    stage: str = "需求"
    created_at: str = ""
    vault_path: str = ""


class RequirementListResponse(BaseModel):
    items: list[RequirementResponse]
    total: int
    page: int
    page_size: int


# --- LLM Extraction Output ---

class ExtractedRequirement(BaseModel):
    title: str
    description: str
    sentiment: SentimentEnum = SentimentEnum.MODERATE
    emotion: EmotionEnum = EmotionEnum.NEUTRAL
    confidence: float = 0.5
    use_case: str = ""
    pain_point: str = ""


# --- Noise Filter ---

class NoiseVerdict(str, Enum):
    RELEVANT = "relevant"
    NOISE = "noise"
    UNSURE = "unsure"


class FilteredItem(BaseModel):
    item: "RawDiscussionItem"
    verdict: NoiseVerdict
    reason: str = ""
    confidence: float = 0.0


# --- Raw Discussion Item (crawler output) ---

class RawDiscussionItem(BaseModel):
    platform: str
    source_url: str
    title: str
    content: str
    author: str = ""
    tags: list[str] = Field(default_factory=list)


# --- Report Schemas (from vault) ---

class ReportResponse(BaseModel):
    title: str
    keyword: str
    content: str
    stage: str = "初稿"
    created_at: str = ""


class ReportListResponse(BaseModel):
    items: list[ReportResponse]
    total: int


# --- Dashboard ---

class DashboardStats(BaseModel):
    total_requirements: int
    total_tasks: int
    platform_distribution: dict[str, int]
    sentiment_distribution: dict[str, int]
    top_keywords: list[str]


# --- Scheduler ---


class ScheduledJobCreateRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    keyword: str = Field(..., min_length=1, max_length=200)
    platforms: list[PlatformEnum] = Field(default_factory=lambda: list(PlatformEnum))
    interval_minutes: int = Field(default=60, ge=10, le=10080)


class ScheduledJobUpdateRequest(BaseModel):
    name: str | None = None
    keyword: str | None = None
    platforms: list[PlatformEnum] | None = None
    interval_minutes: int | None = Field(default=None, ge=10, le=10080)
    status: JobStatus | None = None


class ScheduledJobResponse(BaseModel):
    id: int
    name: str
    keyword: str
    platforms: list[str]
    interval_minutes: int
    status: JobStatus
    last_run_at: str | None = None
    last_task_ids: list[int] | None = None
    run_count: int
    created_at: datetime.datetime
    updated_at: datetime.datetime | None = None

    model_config = ConfigDict(from_attributes=True)


class ScheduledJobListResponse(BaseModel):
    items: list[ScheduledJobResponse]
    total: int


# --- Opportunity Schemas ---

class ScoreDimensions(BaseModel):
    vibe_code_suitability: float = 0.0
    demand_intensity: float = 0.0
    technical_feasibility: float = 0.0
    market_freshness: float = 0.0
    overall: float = 0.0


class TractionSignal(BaseModel):
    source: str = ""
    mention_count: int = 0
    sentiment_strength: float = 0.0
    growth_trend: str = "stable"
    representative_quote: str = ""


class OpportunityResponse(BaseModel):
    id: int
    keyword: str
    title: str
    description: str = ""
    scores: ScoreDimensions = ScoreDimensions()
    traction: list[TractionSignal] = []
    source_req_ids: list[str] = []
    status: str = "pending"
    created_at: str = ""
    updated_at: str = ""

    model_config = ConfigDict(from_attributes=True)


class OpportunityListResponse(BaseModel):
    items: list[OpportunityResponse]
    total: int


class ScoreRequest(BaseModel):
    keyword: str = Field(..., min_length=1, max_length=200)


# --- Proposal Schemas ---

class ProposalGenerateRequest(BaseModel):
    opportunity_id: int = Field(..., gt=0)


class ProposalResponse(BaseModel):
    id: int
    opportunity_id: int | None = None
    keyword: str
    title: str
    problem_statement: str = ""
    target_user: str = ""
    mvp_scope: list[dict] = []
    suggested_stack: dict = {}
    effort_estimate_hours: int = 0
    effort_breakdown: dict = {}
    traction_signals: list[dict] = []
    claude_prompt: str = ""
    risks: list[str] = []
    status: str = "draft"
    vault_path: str | None = None
    created_at: str = ""
    updated_at: str = ""

    model_config = ConfigDict(from_attributes=True)


class ProposalListResponse(BaseModel):
    items: list[ProposalResponse]
    total: int


# --- Entity Link Schemas ---


class EntityLinkCreateRequest(BaseModel):
    """Create a single entity link."""
    source_type: str = Field(..., min_length=1, max_length=50)
    source_id: str = Field(..., min_length=1, max_length=500)
    link_type: LinkType = Field(...)
    target_type: str = Field(..., min_length=1, max_length=50)
    target_id: str = Field(..., min_length=1, max_length=500)
    metadata: dict = Field(default_factory=dict)


class EntityLinkBatchRequest(BaseModel):
    """Batch-create entity links (e.g., during migration or pipeline runs)."""
    links: list[EntityLinkCreateRequest] = Field(..., min_length=1, max_length=500)


class EntityLinkResponse(BaseModel):
    id: int
    source_type: str
    source_id: str
    link_type: str
    target_type: str
    target_id: str
    metadata: dict = Field(default_factory=dict, validation_alias="metadata_json")
    created_at: datetime.datetime
    updated_at: datetime.datetime | None = None

    model_config = ConfigDict(from_attributes=True)


class EntityLinkListResponse(BaseModel):
    items: list[EntityLinkResponse]
    total: int


class EntityLinkQueryRequest(BaseModel):
    """Query links by filter criteria — all fields optional."""
    source_type: str | None = None
    source_id: str | None = None
    link_type: str | None = None
    target_type: str | None = None
    target_id: str | None = None
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=50, ge=1, le=500)
