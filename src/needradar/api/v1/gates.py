"""Quality Gate API — endpoints for human review of pipeline gates."""

from __future__ import annotations

import json

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from needradar.core.database import get_db
from needradar.models.feedback import FeedbackRecord
from needradar.models.quality_gate import GateStatus, QualityGate

router = APIRouter(prefix="/gates", tags=["gates"])


# ── Schemas ──

class GateResponse(BaseModel):
    id: int
    pipeline_run_id: int
    gate_type: str
    status: str
    items_count: int = 0
    human_decision: str | None = None
    reviewer_note: str | None = None
    reviewed_at: str | None = None
    created_at: str = ""
    updated_at: str | None = None


class GateDetailResponse(GateResponse):
    items: list[dict] = []


class GateListResponse(BaseModel):
    items: list[GateResponse]
    total: int


class GateApproveRequest(BaseModel):
    note: str = ""


class GateRejectRequest(BaseModel):
    reason: str = ""


class GateEditRequest(BaseModel):
    edits: list[dict] = []
    note: str = ""


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


# ── Endpoints ──

@router.get("", response_model=GateListResponse)
async def list_gates(
    pipeline_run_id: int | None = None,
    status: str | None = None,
    gate_type: str | None = None,
    db: AsyncSession = Depends(get_db),
):
    """List quality gates with optional filters."""
    stmt = select(QualityGate)
    if pipeline_run_id:
        stmt = stmt.where(QualityGate.pipeline_run_id == pipeline_run_id)
    if status:
        stmt = stmt.where(QualityGate.status == status)
    if gate_type:
        stmt = stmt.where(QualityGate.gate_type == gate_type)
    stmt = stmt.order_by(QualityGate.created_at.desc())

    result = await db.execute(stmt)
    gates = result.scalars().all()

    return GateListResponse(
        items=[_to_gate_response(g) for g in gates],
        total=len(gates),
    )


@router.get("/{gate_id}", response_model=GateDetailResponse)
async def get_gate(gate_id: int, db: AsyncSession = Depends(get_db)):
    """Get gate detail with items under review."""
    gate = await db.get(QualityGate, gate_id)
    if not gate:
        raise HTTPException(404, "Gate not found")

    items = json.loads(gate.items_json) if gate.items_json else []
    resp = _to_gate_response(gate)
    return GateDetailResponse(**resp.model_dump(), items=items)


@router.post("/{gate_id}/approve", response_model=GateResponse)
async def approve_gate(gate_id: int, req: GateApproveRequest, db: AsyncSession = Depends(get_db)):
    """Approve a gate and advance the pipeline."""
    from needradar.services.pipeline_orchestrator import PipelineOrchestrator
    orchestrator = PipelineOrchestrator(db)
    try:
        await orchestrator.resume_after_gate(gate_id, "approve", note=req.note)
    except ValueError as e:
        raise HTTPException(400, str(e))
    gate = await db.get(QualityGate, gate_id)
    return _to_gate_response(gate)


@router.post("/{gate_id}/reject", response_model=GateResponse)
async def reject_gate(gate_id: int, req: GateRejectRequest, db: AsyncSession = Depends(get_db)):
    """Reject a gate and stop the pipeline."""
    from needradar.services.pipeline_orchestrator import PipelineOrchestrator
    orchestrator = PipelineOrchestrator(db)
    try:
        await orchestrator.resume_after_gate(gate_id, "reject", note=req.reason)
    except ValueError as e:
        raise HTTPException(400, str(e))
    gate = await db.get(QualityGate, gate_id)
    return _to_gate_response(gate)


@router.post("/{gate_id}/edit", response_model=GateResponse)
async def edit_gate(gate_id: int, req: GateEditRequest, db: AsyncSession = Depends(get_db)):
    """Submit edits and approve the gate."""
    from needradar.services.pipeline_orchestrator import PipelineOrchestrator
    orchestrator = PipelineOrchestrator(db)
    try:
        await orchestrator.resume_after_gate(gate_id, "edit", edits=req.edits, note=req.note)
    except ValueError as e:
        raise HTTPException(400, str(e))
    gate = await db.get(QualityGate, gate_id)
    return _to_gate_response(gate)


@router.get("/{gate_id}/feedback", response_model=FeedbackListResponse)
async def list_gate_feedback(gate_id: int, db: AsyncSession = Depends(get_db)):
    """List feedback records for a gate."""
    result = await db.execute(
        select(FeedbackRecord).where(FeedbackRecord.gate_id == gate_id)
    )
    feedbacks = result.scalars().all()
    return FeedbackListResponse(
        items=[_to_feedback_response(f) for f in feedbacks],
        total=len(feedbacks),
    )


# ── Helpers ──

def _to_gate_response(g: QualityGate) -> GateResponse:
    items = json.loads(g.items_json) if g.items_json else []
    return GateResponse(
        id=g.id,
        pipeline_run_id=g.pipeline_run_id,
        gate_type=g.gate_type,
        status=g.status,
        items_count=len(items),
        human_decision=g.human_decision,
        reviewer_note=g.reviewer_note,
        reviewed_at=g.reviewed_at,
        created_at=str(g.created_at) if g.created_at else "",
        updated_at=str(g.updated_at) if g.updated_at else None,
    )


def _to_feedback_response(f: FeedbackRecord) -> FeedbackResponse:
    return FeedbackResponse(
        id=f.id,
        pipeline_run_id=f.pipeline_run_id,
        gate_id=f.gate_id,
        feedback_type=f.feedback_type,
        entity_type=f.entity_type,
        entity_id=f.entity_id,
        before=json.loads(f.before_json) if f.before_json else None,
        after=json.loads(f.after_json) if f.after_json else None,
        reason=f.reason,
        created_at=str(f.created_at) if f.created_at else "",
    )
