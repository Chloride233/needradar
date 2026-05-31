from __future__ import annotations

import datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field

from needradar.models.crawl_task import TaskStatus


# --- Enums ---

class PlatformEnum(str, Enum):
    GITHUB = "github"
    STACKOVERFLOW = "stackoverflow"
    JUEJIN = "juejin"
    BILIBILI = "bilibili"


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
    error_message: str | None
    report_path: str | None = None
    created_at: datetime.datetime
    updated_at: datetime.datetime | None = None

    model_config = ConfigDict(from_attributes=True)


class TaskListResponse(BaseModel):
    items: list[TaskResponse]
    total: int


# --- Requirement Schemas (from vault frontmatter) ---

class RequirementResponse(BaseModel):
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

from needradar.models.scheduled_job import JobStatus


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
