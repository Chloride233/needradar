from __future__ import annotations

import asyncio
import json

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from loguru import logger
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sse_starlette.sse import EventSourceResponse

from needradar.core import database as db_module
from needradar.core.database import get_db
from needradar.models.crawl_task import CrawlTask, TaskStatus
from needradar.schemas.schemas import TaskCreateRequest, TaskListResponse, TaskResponse

router = APIRouter(prefix="/tasks", tags=["tasks"])


@router.get("/platforms")
async def list_platforms():
    from needradar.crawlers.factory import available_platforms
    return {"platforms": available_platforms()}


async def _retry_commit(db: AsyncSession, retries: int = 5, delay: float = 1.0) -> None:
    for attempt in range(retries):
        try:
            await db.commit()
            return
        except Exception as e:
            await db.rollback()
            if attempt < retries - 1:
                logger.warning("commit_retry", attempt=attempt + 1, error=str(e))
                await asyncio.sleep(delay * (attempt + 1))
            else:
                raise


async def _run_pipeline(keyword: str, task_ids: list[int]) -> None:
    import traceback

    from needradar.services.analysis_service import AnalysisService

    logger.info("background_pipeline_start", keyword=keyword, task_ids=task_ids)
    await asyncio.sleep(1)
    try:
        async with db_module.async_session_factory() as db:
            service = AnalysisService(db)
            await service.run_pipeline(keyword, [], existing_task_ids=task_ids)
            await _retry_commit(db)

            # Auto-generate report after pipeline completes
            report_path = None
            try:
                from needradar.services.report_service import get_report_service
                rs = get_report_service()
                report_path = await rs.generate_report(keyword)
                report_name = report_path.name

                # Attach report path to all tasks in this batch
                tasks = (await db.execute(
                    select(CrawlTask).where(CrawlTask.id.in_(task_ids))
                )).scalars().all()
                for t in tasks:
                    t.report_path = report_name
                await _retry_commit(db)
                logger.info("auto_report_generated", keyword=keyword, report=report_name)
            except Exception as e:
                logger.warning("auto_report_failed", keyword=keyword, error=str(e))

            # Auto-verify the generated report
            if report_path is not None:
                try:
                    from needradar.models.verification import VerificationResult, VerificationStatus
                    from needradar.services.content_verifier import get_verifier
                    report_title = report_path.stem
                    verifier = get_verifier()
                    v_output = await verifier.verify_report(report_title)

                    async with db_module.async_session_factory() as vdb:
                        v_result = VerificationResult(
                            report_title=report_title,
                            status=VerificationStatus.COMPLETED,
                            overall_score=v_output.overall_score,
                            fact_check_score=v_output.fact_check_score,
                            consistency_score=v_output.consistency_score,
                            source_reliability_score=v_output.source_reliability_score,
                            total_claims=len(v_output.claims),
                            hallucination_count=v_output.hallucination_count,
                            flagged_count=v_output.flagged_count,
                            claims_json=json.dumps(
                                [c.__dict__ for c in v_output.claims], ensure_ascii=False
                            ),
                            suggestions_json=json.dumps(
                                v_output.suggestions, ensure_ascii=False
                            ),
                        )
                        vdb.add(v_result)
                        from needradar.models.llm_usage import LLMUsage
                        for u in verifier._usage_records:
                            vdb.add(LLMUsage(**u))
                        await vdb.commit()
                    logger.info(
                        "auto_verify_done",
                        keyword=keyword,
                        score=v_output.overall_score,
                        hallu=v_output.hallucination_count,
                    )
                except Exception as e:
                    logger.warning("auto_verify_failed", keyword=keyword, error=str(e))

        logger.info("background_pipeline_done", keyword=keyword)
    except Exception as e:
        logger.error("background_pipeline_error", error=str(e))
        traceback.print_exc()


@router.post("", response_model=TaskListResponse, status_code=201)
async def create_task(
    request: TaskCreateRequest,
    background_tasks: BackgroundTasks,
    mode: str = "auto",
    db: AsyncSession = Depends(get_db),
):
    """
    Create a crawl task.

    mode: "auto" (default) = fire-and-forget pipeline
          "agent" = gate-aware pipeline with human confirmation
    """
    if not request.platforms:
        raise HTTPException(status_code=400, detail="至少选择一个平台")

    # Auto-cleanup stale tasks (pending/running > 1 hour)
    from datetime import datetime, timedelta, timezone
    cutoff = datetime.now(timezone.utc) - timedelta(hours=1)
    stale = (await db.execute(
        select(CrawlTask).where(
            CrawlTask.status.in_([TaskStatus.PENDING, TaskStatus.RUNNING]),
            CrawlTask.updated_at < cutoff,
        )
    )).scalars().all()
    for t in stale:
        t.status = TaskStatus.FAILED
        t.error_message = "任务超时，已自动清理"
    if stale:
        await db.flush()

    if mode == "agent":
        # Agent mode: use PipelineOrchestrator with quality gates
        from needradar.services.pipeline_orchestrator import PipelineOrchestrator
        orchestrator = PipelineOrchestrator(db)
        platforms = [p.value for p in request.platforms]
        run = await orchestrator.start(request.keyword, platforms)
        # Return tasks from the orchestrator's run
        task_ids = json.loads(run.task_ids_json)
        tasks = []
        for tid in task_ids:
            task = await db.get(CrawlTask, tid)
            if task:
                tasks.append(task)
        return TaskListResponse(
            items=[TaskResponse.model_validate(t) for t in tasks],
            total=len(tasks),
        )

    # Auto mode: fire-and-forget (existing behavior)
    tasks: list[CrawlTask] = []
    for platform in request.platforms:
        task = CrawlTask(keyword=request.keyword, platform=platform.value, status=TaskStatus.PENDING)
        db.add(task)
        tasks.append(task)
    await db.flush()
    task_ids = [t.id for t in tasks]
    await db.commit()

    background_tasks.add_task(_run_pipeline, request.keyword, task_ids)

    return TaskListResponse(
        items=[TaskResponse.model_validate(t) for t in tasks],
        total=len(tasks),
    )


@router.get("", response_model=TaskListResponse)
async def list_tasks(
    keyword: str | None = None,
    status: TaskStatus | None = None,
    page: int = 1,
    page_size: int = 20,
    db: AsyncSession = Depends(get_db),
):
    stmt = select(CrawlTask)
    count_stmt = select(func.count()).select_from(CrawlTask)

    if keyword:
        stmt = stmt.where(CrawlTask.keyword == keyword)
        count_stmt = count_stmt.where(CrawlTask.keyword == keyword)
    if status:
        stmt = stmt.where(CrawlTask.status == status)
        count_stmt = count_stmt.where(CrawlTask.status == status)

    total = (await db.execute(count_stmt)).scalar() or 0
    stmt = stmt.order_by(CrawlTask.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(stmt)
    tasks = result.scalars().all()

    return TaskListResponse(
        items=[TaskResponse.model_validate(t) for t in tasks],
        total=total,
    )


@router.get("/sse/stream")
async def task_sse_stream():
    async def event_generator():
        while True:
            async with db_module.async_session_factory() as db:
                stmt = select(CrawlTask).order_by(CrawlTask.created_at.desc()).limit(50)
                result = await db.execute(stmt)
                tasks = [TaskResponse.model_validate(t).model_dump(mode="json") for t in result.scalars().all()]
            yield {"event": "tasks", "data": json.dumps(tasks)}
            has_running = any(t["status"] in ("pending", "running") for t in tasks)
            await asyncio.sleep(2 if has_running else 10)

    return EventSourceResponse(event_generator())


@router.get("/{task_id}", response_model=TaskResponse)
async def get_task(task_id: int, db: AsyncSession = Depends(get_db)):
    task = await db.get(CrawlTask, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return TaskResponse.model_validate(task)


@router.post("/vault/index")
async def index_vault_endpoint(force: bool = False):
    """Index vault markdown files into LanceDB for RAG retrieval."""
    from needradar.services.vault_vectorizer import index_vault
    try:
        stats = await index_vault(force=force)
        return {"status": "ok", **stats}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
