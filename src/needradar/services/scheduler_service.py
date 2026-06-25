from __future__ import annotations

import json
from datetime import datetime, timezone

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from loguru import logger

_scheduler: AsyncIOScheduler | None = None


def get_scheduler() -> AsyncIOScheduler:
    global _scheduler
    if _scheduler is None:
        _scheduler = AsyncIOScheduler(timezone="UTC", job_defaults={"coalesce": True, "max_instances": 1})
    return _scheduler


def start_scheduler() -> None:
    sched = get_scheduler()
    if not sched.running:
        sched.start()
        logger.info("scheduler_started")


def stop_scheduler() -> None:
    sched = get_scheduler()
    if sched.running:
        sched.shutdown(wait=False)
        logger.info("scheduler_stopped")


async def restore_jobs() -> None:
    from needradar.core.database import async_session_factory
    from needradar.models.scheduled_job import JobStatus, ScheduledJob

    sched = get_scheduler()
    async with async_session_factory() as db:
        from sqlalchemy import select
        result = await db.execute(
            select(ScheduledJob).where(ScheduledJob.status == JobStatus.ACTIVE)
        )
        jobs = result.scalars().all()
        for job in jobs:
            _add_job_to_scheduler(sched, job)
        if jobs:
            logger.info("scheduler_jobs_restored", count=len(jobs))


def _job_id(scheduled_job_id: int) -> str:
    return f"nr_job_{scheduled_job_id}"


def _add_job_to_scheduler(sched: AsyncIOScheduler, job) -> None:
    job_id = _job_id(job.id)
    try:
        sched.remove_job(job_id)
    except Exception:
        pass
    sched.add_job(
        _execute_scheduled_job,
        trigger=IntervalTrigger(minutes=job.interval_minutes),
        id=job_id,
        args=[job.id],
        replace_existing=True,
    )
    logger.debug("scheduler_job_added", job_id=job.id, interval=job.interval_minutes)


def remove_job(scheduled_job_id: int) -> None:
    sched = get_scheduler()
    try:
        sched.remove_job(_job_id(scheduled_job_id))
    except Exception:
        pass


def reschedule_job(scheduled_job_id: int, interval_minutes: int) -> None:
    sched = get_scheduler()
    job_id = _job_id(scheduled_job_id)
    try:
        sched.reschedule_job(job_id, trigger=IntervalTrigger(minutes=interval_minutes))
    except Exception:
        # Job might not exist in scheduler (e.g. paused), re-add
        pass


async def _execute_scheduled_job(scheduled_job_id: int) -> None:
    import traceback

    from needradar.core.database import async_session_factory
    from needradar.models.scheduled_job import ScheduledJob
    from needradar.schemas.schemas import PlatformEnum

    logger.info("scheduled_job_executing", job_id=scheduled_job_id)

    try:
        async with async_session_factory() as db:
            job = await db.get(ScheduledJob, scheduled_job_id)
            if not job:
                logger.warning("scheduled_job_not_found", job_id=scheduled_job_id)
                return

            platforms = [p for p in json.loads(job.platforms) if p in PlatformEnum._value2member_map_]
            if not platforms:
                logger.warning("scheduled_job_no_platforms", job_id=scheduled_job_id)
                return

            # Create tasks via the tasks API's pipeline logic
            import asyncio

            from needradar.api.v1.tasks import _run_pipeline
            from needradar.models.crawl_task import CrawlTask, TaskStatus

            tasks: list[CrawlTask] = []
            for platform in platforms:
                task = CrawlTask(keyword=job.keyword, platform=platform, status=TaskStatus.PENDING)
                db.add(task)
                tasks.append(task)
            await db.commit()

            task_ids = [t.id for t in tasks]

            # Update job metadata
            job.last_run_at = datetime.now(timezone.utc).isoformat()
            job.last_task_ids = json.dumps(task_ids)
            job.run_count += 1
            await db.commit()

            # Run pipeline in background
            asyncio.create_task(_run_pipeline(job.keyword, task_ids))
            logger.info("scheduled_job_dispatched", job_id=scheduled_job_id, task_ids=task_ids)

    except Exception as e:
        logger.error("scheduled_job_failed", job_id=scheduled_job_id, error=str(e))
        traceback.print_exc()
