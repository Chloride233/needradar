"""Shared Pydantic schemas for the Agent closed-loop system."""

from __future__ import annotations

from pydantic import BaseModel


class FeedbackResponse(BaseModel):
    id: int
    pipeline_run_id: int
    gate_id: int
    feedback_type: str
    entity_type: str
    entity_id: str
    before: dict | None = None
    after: dict | None = None
    reason: str | None = None
    created_at: str = ""


class FeedbackListResponse(BaseModel):
    items: list[FeedbackResponse]
    total: int


class FeedbackStatsResponse(BaseModel):
    total: int
    by_type: dict[str, int]
    by_entity: dict[str, int]
