"""Agent status aggregation endpoint — single source of truth for the dashboard."""

from __future__ import annotations

import json

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from needradar.core.database import get_db
from needradar.models.pipeline_run import PipelineRun
from needradar.models.quality_gate import GateStatus, QualityGate

router = APIRouter(prefix="/agent", tags=["agent"])


@router.get("/status")
async def agent_status(db: AsyncSession = Depends(get_db)):
    """Aggregate endpoint: active runs, pending gates, recent completed, stats."""

    # ── Active runs (running or paused) ──
    active_stmt = (
        select(PipelineRun)
        .where(PipelineRun.status.in_(["running", "paused"]))
        .order_by(PipelineRun.updated_at.desc())
        .limit(10)
    )
    active_result = await db.execute(active_stmt)
    active_runs = []
    for r in active_result.scalars().all():
        try:
            stages = json.loads(r.stages_json)
        except (json.JSONDecodeError, TypeError):
            stages = []
        active_runs.append({
            "id": r.id,
            "keyword": r.keyword,
            "status": r.status,
            "current_phase": r.current_phase,
            "gate_status": r.gate_status,
            "is_agent_mode": r.is_agent_mode,
            "stages": stages,
            "created_at": str(r.created_at),
            "updated_at": str(r.updated_at),
        })

    # ── Pending gates (awaiting_review) — batch fetch run keywords ──
    gates_stmt = (
        select(QualityGate)
        .where(QualityGate.status == GateStatus.AWAITING_REVIEW)
        .order_by(QualityGate.created_at.desc())
        .limit(10)
    )
    gates_result = await db.execute(gates_stmt)
    gate_rows = gates_result.scalars().all()

    # Batch fetch associated runs to avoid N+1
    run_ids = list({g.pipeline_run_id for g in gate_rows})
    runs_map: dict[int, str] = {}
    if run_ids:
        runs_result = await db.execute(
            select(PipelineRun).where(PipelineRun.id.in_(run_ids))
        )
        for r in runs_result.scalars().all():
            runs_map[r.id] = r.keyword

    pending_gates = []
    for g in gate_rows:
        pending_gates.append({
            "id": g.id,
            "pipeline_run_id": g.pipeline_run_id,
            "gate_type": g.gate_type,
            "status": g.status,
            "items_count": g.items_count or 0,
            "keyword": runs_map.get(g.pipeline_run_id),
            "created_at": str(g.created_at),
        })

    # ── Recent completed runs (latest 5) ──
    completed_stmt = (
        select(PipelineRun)
        .where(PipelineRun.status == "completed")
        .order_by(PipelineRun.updated_at.desc())
        .limit(5)
    )
    completed_result = await db.execute(completed_stmt)
    recent_completed = []
    for r in completed_result.scalars().all():
        recent_completed.append({
            "id": r.id,
            "keyword": r.keyword,
            "status": r.status,
            "is_agent_mode": r.is_agent_mode,
            "created_at": str(r.created_at),
            "updated_at": str(r.updated_at),
        })

    # ── Stats ──
    total_runs = (await db.execute(
        select(func.count()).select_from(PipelineRun)
    )).scalar() or 0

    total_gates = (await db.execute(
        select(func.count()).select_from(QualityGate)
    )).scalar() or 0

    approved_gates = (await db.execute(
        select(func.count()).select_from(QualityGate).where(
            QualityGate.status == GateStatus.APPROVED
        )
    )).scalar() or 0

    rejected_gates = (await db.execute(
        select(func.count()).select_from(QualityGate).where(
            QualityGate.status == GateStatus.REJECTED
        )
    )).scalar() or 0

    return {
        "active_runs": active_runs,
        "pending_gates": pending_gates,
        "recent_completed": recent_completed,
        "stats": {
            "total_runs": total_runs,
            "total_gates": total_gates,
            "approved_gates": approved_gates,
            "rejected_gates": rejected_gates,
            "pending_gates_count": len(pending_gates),
        },
    }
