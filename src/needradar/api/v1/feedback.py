"""Feedback API — view and manage structured feedback from quality gates."""

from __future__ import annotations

import json

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from needradar.core.database import get_db
from needradar.models.feedback import FeedbackRecord
from needradar.services.feedback_service import FeedbackService

router = APIRouter(prefix="/feedback", tags=["feedback"])


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


@router.get("", response_model=FeedbackListResponse)
async def list_feedback(
    pipeline_run_id: int | None = None,
    feedback_type: str | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    """List all feedback records with optional filters."""
    svc = FeedbackService(db)
    records = await svc.get_all_feedback(pipeline_run_id=pipeline_run_id, limit=page_size * page)
    # Apply type filter in Python (simple for single-user)
    if feedback_type:
        records = [r for r in records if r.feedback_type == feedback_type]
    total = len(records)
    start = (page - 1) * page_size
    page_records = records[start:start + page_size]
    return FeedbackListResponse(
        items=[_to_response(r) for r in page_records],
        total=total,
    )


@router.get("/stats", response_model=FeedbackStatsResponse)
async def feedback_stats(db: AsyncSession = Depends(get_db)):
    """Aggregate feedback statistics."""
    svc = FeedbackService(db)
    records = await svc.get_all_feedback(limit=10000)
    by_type: dict[str, int] = {}
    by_entity: dict[str, int] = {}
    for r in records:
        by_type[r.feedback_type] = by_type.get(r.feedback_type, 0) + 1
        by_entity[r.entity_type] = by_entity.get(r.entity_type, 0) + 1
    return FeedbackStatsResponse(
        total=len(records),
        by_type=by_type,
        by_entity=by_entity,
    )


@router.get("/derived-test-cases")
async def get_derived_test_cases(
    min_corrections: int = Query(1, ge=1),
    db: AsyncSession = Depends(get_db),
):
    """Preview test cases derived from feedback (for prompt optimization)."""
    svc = FeedbackService(db)
    test_cases = await svc.derive_test_cases_from_feedback(min_corrections=min_corrections)
    return {"test_cases": test_cases, "count": len(test_cases)}


def _to_response(r: FeedbackRecord) -> FeedbackResponse:
    return FeedbackResponse(
        id=r.id,
        pipeline_run_id=r.pipeline_run_id,
        gate_id=r.gate_id,
        feedback_type=r.feedback_type,
        entity_type=r.entity_type,
        entity_id=r.entity_id,
        before=json.loads(r.before_json) if r.before_json else None,
        after=json.loads(r.after_json) if r.after_json else None,
        reason=r.reason,
        created_at=str(r.created_at) if r.created_at else "",
    )
