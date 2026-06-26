"""API for pipeline run tracking — list, detail, resume."""

from __future__ import annotations

import json

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from needradar.core.database import get_db
from needradar.models.pipeline_run import PipelineRun

router = APIRouter(prefix="/pipeline", tags=["pipeline"])


@router.get("/runs")
async def list_runs(
    status: str = Query(""),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    query = select(PipelineRun)
    count_query = select(func.count()).select_from(PipelineRun)
    if status:
        statuses = [s.strip() for s in status.split(",") if s.strip()]
        if len(statuses) == 1:
            query = query.where(PipelineRun.status == statuses[0])
            count_query = count_query.where(PipelineRun.status == statuses[0])
        elif statuses:
            query = query.where(PipelineRun.status.in_(statuses))
            count_query = count_query.where(PipelineRun.status.in_(statuses))

    total = (await db.execute(count_query)).scalar() or 0
    query = query.order_by(PipelineRun.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(query)
    rows = result.scalars().all()

    items = []
    for r in rows:
        try:
            stages = json.loads(r.stages_json)
            tids = json.loads(r.task_ids_json)
        except json.JSONDecodeError:
            stages, tids = [], []
        items.append({
            "id": r.id, "keyword": r.keyword, "status": r.status,
            "stages": stages, "task_ids": tids, "error_message": r.error_message,
            "current_phase": r.current_phase, "gate_status": r.gate_status,
            "is_agent_mode": r.is_agent_mode,
            "created_at": str(r.created_at), "updated_at": str(r.updated_at),
        })
    return {"items": items, "total": total}


@router.get("/runs/{run_id}")
async def get_run(run_id: int, db: AsyncSession = Depends(get_db)):
    r = await db.get(PipelineRun, run_id)
    if not r:
        raise HTTPException(status_code=404, detail="Pipeline run not found")
    try:
        stages = json.loads(r.stages_json); tids = json.loads(r.task_ids_json)
    except json.JSONDecodeError:
        stages, tids = [], []
    return {
        "id": r.id, "keyword": r.keyword, "status": r.status,
        "stages": stages, "task_ids": tids, "error_message": r.error_message,
        "current_phase": r.current_phase, "gate_status": r.gate_status,
        "is_agent_mode": r.is_agent_mode,
        "created_at": str(r.created_at), "updated_at": str(r.updated_at),
    }


@router.post("/runs/{run_id}/resume")
async def resume_run(run_id: int, db: AsyncSession = Depends(get_db)):
    r = await db.get(PipelineRun, run_id)
    if not r:
        raise HTTPException(status_code=404, detail="Pipeline run not found")
    if r.status not in ("failed", "pending"):
        raise HTTPException(status_code=400, detail=f"Cannot resume with status '{r.status}'")

    from needradar.services.analysis_service import AnalysisService
    svc = AnalysisService(db)
    tasks = await svc.run_pipeline(r.keyword, ["github", "stackoverflow", "juejin"])
    r.status = "completed"
    r.task_ids_json = json.dumps([t.id for t in tasks], ensure_ascii=False)
    await db.flush()
    return {"id": r.id, "status": r.status, "message": f"Resumed pipeline for '{r.keyword}'"}
