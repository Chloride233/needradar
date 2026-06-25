from __future__ import annotations

import json

from fastapi import APIRouter, Depends, HTTPException
from loguru import logger
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from needradar.core.database import get_db
from needradar.models.scheduled_job import JobStatus, ScheduledJob
from needradar.schemas.schemas import (
    PlatformEnum,
    ScheduledJobCreateRequest,
    ScheduledJobListResponse,
    ScheduledJobResponse,
    ScheduledJobUpdateRequest,
)
from needradar.services.scheduler_service import (
    _add_job_to_scheduler,
    get_scheduler,
    remove_job,
    reschedule_job,
)

router = APIRouter(prefix="/scheduler", tags=["scheduler"])


def _parse_job(job: ScheduledJob) -> dict:
    platforms = json.loads(job.platforms)
    last_task_ids = json.loads(job.last_task_ids) if job.last_task_ids else None
    return {
        "id": job.id,
        "name": job.name,
        "keyword": job.keyword,
        "platforms": platforms,
        "interval_minutes": job.interval_minutes,
        "status": job.status,
        "last_run_at": job.last_run_at,
        "last_task_ids": last_task_ids,
        "run_count": job.run_count,
        "created_at": job.created_at,
        "updated_at": job.updated_at,
    }


@router.post("", response_model=ScheduledJobResponse, status_code=201)
async def create_job(
    request: ScheduledJobCreateRequest,
    db: AsyncSession = Depends(get_db),
):
    platforms_json = json.dumps([p.value for p in request.platforms])
    job = ScheduledJob(
        name=request.name,
        keyword=request.keyword,
        platforms=platforms_json,
        interval_minutes=request.interval_minutes,
        status=JobStatus.ACTIVE,
    )
    db.add(job)
    await db.flush()
    await db.commit()
    await db.refresh(job)

    _add_job_to_scheduler(get_scheduler(), job)
    logger.info("scheduler_job_created", job_id=job.id, keyword=job.keyword)

    return _parse_job(job)


@router.get("", response_model=ScheduledJobListResponse)
async def list_jobs(
    page: int = 1,
    page_size: int = 50,
    db: AsyncSession = Depends(get_db),
):
    count_stmt = select(func.count()).select_from(ScheduledJob)
    total = (await db.execute(count_stmt)).scalar() or 0

    stmt = (
        select(ScheduledJob)
        .order_by(ScheduledJob.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    result = await db.execute(stmt)
    jobs = result.scalars().all()

    return ScheduledJobListResponse(
        items=[ScheduledJobResponse(**_parse_job(j)) for j in jobs],
        total=total,
    )


@router.get("/{job_id}", response_model=ScheduledJobResponse)
async def get_job(job_id: int, db: AsyncSession = Depends(get_db)):
    job = await db.get(ScheduledJob, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="定时任务不存在")
    return _parse_job(job)


@router.patch("/{job_id}", response_model=ScheduledJobResponse)
async def update_job(
    job_id: int,
    request: ScheduledJobUpdateRequest,
    db: AsyncSession = Depends(get_db),
):
    job = await db.get(ScheduledJob, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="定时任务不存在")

    if request.name is not None:
        job.name = request.name
    if request.keyword is not None:
        job.keyword = request.keyword
    if request.platforms is not None:
        job.platforms = json.dumps([p.value for p in request.platforms])
    if request.interval_minutes is not None:
        job.interval_minutes = request.interval_minutes
    if request.status is not None:
        job.status = request.status

    await db.commit()
    await db.refresh(job)

    # Sync scheduler
    if job.status == JobStatus.ACTIVE:
        _add_job_to_scheduler(get_scheduler(), job)
    else:
        remove_job(job.id)

    logger.info("scheduler_job_updated", job_id=job.id)
    return _parse_job(job)


@router.delete("/{job_id}", status_code=204)
async def delete_job(job_id: int, db: AsyncSession = Depends(get_db)):
    job = await db.get(ScheduledJob, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="定时任务不存在")

    remove_job(job.id)
    await db.delete(job)
    await db.commit()
    logger.info("scheduler_job_deleted", job_id=job_id)


@router.post("/{job_id}/trigger", response_model=ScheduledJobResponse)
async def trigger_job(job_id: int, db: AsyncSession = Depends(get_db)):
    from needradar.services.scheduler_service import _execute_scheduled_job
    import asyncio

    job = await db.get(ScheduledJob, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="定时任务不存在")

    asyncio.get_event_loop().create_task(_execute_scheduled_job(job.id))
    logger.info("scheduler_job_triggered", job_id=job_id)

    await db.refresh(job)
    return _parse_job(job)
