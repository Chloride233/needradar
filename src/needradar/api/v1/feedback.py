"""Feedback API — view and manage structured feedback from quality gates."""

from __future__ import annotations

import json

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from needradar.core.database import get_db
from needradar.models.feedback import FeedbackRecord
from needradar.schemas.agent_schemas import (
    FeedbackListResponse,
    FeedbackResponse,
    FeedbackStatsResponse,
)

router = APIRouter(prefix="/feedback", tags=["feedback"])


@router.get("", response_model=FeedbackListResponse)
async def list_feedback(
    pipeline_run_id: int | None = None,
    feedback_type: str | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    """List all feedback records with optional filters (SQL-based pagination)."""
    stmt = select(FeedbackRecord)
    count_stmt = select(func.count()).select_from(FeedbackRecord)

    if pipeline_run_id:
        stmt = stmt.where(FeedbackRecord.pipeline_run_id == pipeline_run_id)
        count_stmt = count_stmt.where(FeedbackRecord.pipeline_run_id == pipeline_run_id)
    if feedback_type:
        stmt = stmt.where(FeedbackRecord.feedback_type == feedback_type)
        count_stmt = count_stmt.where(FeedbackRecord.feedback_type == feedback_type)

    total = (await db.execute(count_stmt)).scalar() or 0
    stmt = stmt.order_by(FeedbackRecord.created_at.desc())
    stmt = stmt.offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(stmt)
    records = result.scalars().all()

    return FeedbackListResponse(
        items=[_to_response(r) for r in records],
        total=total,
    )


@router.get("/stats", response_model=FeedbackStatsResponse)
async def feedback_stats(db: AsyncSession = Depends(get_db)):
    """Aggregate feedback statistics using SQL GROUP BY."""
    # Count by type
    type_result = await db.execute(
        select(FeedbackRecord.feedback_type, func.count())
        .group_by(FeedbackRecord.feedback_type)
    )
    by_type = {row[0]: row[1] for row in type_result.all()}

    # Count by entity
    entity_result = await db.execute(
        select(FeedbackRecord.entity_type, func.count())
        .group_by(FeedbackRecord.entity_type)
    )
    by_entity = {row[0]: row[1] for row in entity_result.all()}

    total = sum(by_type.values())
    return FeedbackStatsResponse(total=total, by_type=by_type, by_entity=by_entity)


@router.get("/derived-test-cases")
async def get_derived_test_cases(
    min_corrections: int = Query(1, ge=1),
    db: AsyncSession = Depends(get_db),
):
    """Preview test cases derived from feedback (for prompt optimization)."""
    from needradar.services.feedback_service import FeedbackService
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
