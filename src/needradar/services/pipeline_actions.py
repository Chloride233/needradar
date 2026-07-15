"""Burr Actions for the NeedRadar pipeline.

Each action corresponds to a pipeline phase. Actions read from Burr State
and write results back. Quality gates are handled as Burr interrupts.
"""

from __future__ import annotations

import asyncio
import json
from datetime import datetime, timezone

from loguru import logger
from sqlalchemy import select

from needradar.core.database import async_session_factory
from needradar.models.crawl_task import CrawlTask, TaskStatus
from needradar.models.pipeline_phase import PhaseName, PhaseStatus, PipelinePhase
from needradar.models.pipeline_run import PipelineRun
from needradar.models.quality_gate import GateStatus, GateType, QualityGate
from needradar.schemas.schemas import NoiseVerdict, RawDiscussionItem

# ── Helpers (shared across actions) ──


async def _record_phase(run_id: int, phase: PhaseName, status: PhaseStatus, result: dict | None = None) -> None:
    """Record or update a pipeline phase execution."""
    async with async_session_factory() as db:
        now = datetime.now(timezone.utc).isoformat()
        existing_result = await db.execute(
            select(PipelinePhase).where(
                PipelinePhase.pipeline_run_id == run_id,
                PipelinePhase.phase == phase.value,
            )
        )
        existing = existing_result.scalar_one_or_none()

        if existing:
            existing.status = status.value
            if status == PhaseStatus.RUNNING:
                existing.started_at = now
            elif status in (PhaseStatus.COMPLETED, PhaseStatus.FAILED):
                existing.completed_at = now
            if result:
                existing.result_json = json.dumps(result, ensure_ascii=False)
        else:
            db.add(
                PipelinePhase(
                    pipeline_run_id=run_id,
                    phase=phase.value,
                    status=status.value,
                    started_at=now if status == PhaseStatus.RUNNING else None,
                    completed_at=now if status in (PhaseStatus.COMPLETED, PhaseStatus.FAILED) else None,
                    result_json=json.dumps(result, ensure_ascii=False) if result else None,
                )
            )

        await db.commit()


async def _create_gate(run_id: int, gate_type: GateType, items: list[dict]) -> None:
    """Create a quality gate and pause the pipeline."""
    async with async_session_factory() as db:
        run = await db.get(PipelineRun, run_id)
        if not run:
            return

        gate = QualityGate(
            pipeline_run_id=run_id,
            gate_type=gate_type.value,
            status=GateStatus.AWAITING_REVIEW.value,
            items_json=json.dumps(items, ensure_ascii=False),
            items_count=len(items),
        )
        db.add(gate)
        run.current_phase = f"{gate_type.value}_gate"
        run.gate_status = "awaiting_review"
        run.status = "paused"
        await db.commit()
        logger.info("gate_created", run_id=run_id, gate_type=gate_type.value, items=len(items))


async def _update_run(run_id: int, **kwargs) -> None:
    """Update pipeline run fields."""
    async with async_session_factory() as db:
        run = await db.get(PipelineRun, run_id)
        if not run:
            return
        for k, v in kwargs.items():
            setattr(run, k, v)
        await db.commit()


# ── Burr Actions ──


async def crawl_action(run_id: int, keyword: str, platforms: list[str]) -> dict:
    """Crawl phase: fetch raw items from platforms, filter noise, create material gate."""
    from needradar.crawlers.factory import create_crawler
    from needradar.services.crawl_reliability import filter_new_items, save_fingerprints
    from needradar.services.noise_filter import NoiseFilter
    from needradar.services.vault_store import vault

    await _update_run(run_id, current_phase=PhaseName.CRAWLING.value, status="running")
    await _record_phase(run_id, PhaseName.CRAWLING, PhaseStatus.RUNNING)

    all_clean_items: list[dict] = []

    async with async_session_factory() as db:
        run = await db.get(PipelineRun, run_id)
        if not run:
            return {"error": "Run not found"}

        task_ids = json.loads(run.task_ids_json)
        tasks = []
        for tid in task_ids:
            task = await db.get(CrawlTask, tid)
            if task:
                tasks.append(task)

        for task in tasks:
            crawler = create_crawler(task.platform)
            try:
                task.status = TaskStatus.RUNNING
                await db.commit()

                raw_items = await asyncio.wait_for(crawler.crawl(keyword), timeout=30 * 60)
                task.total_items = len(raw_items)

                new_items, skipped = await filter_new_items(db, keyword, task.platform, raw_items)
                task.new_items = len(new_items)
                task.skipped_items = skipped

                save_fingerprints(db, keyword, task.platform, new_items)

                logger.info(
                    "crawl_done",
                    platform=task.platform,
                    total=len(raw_items),
                    new=len(new_items),
                    skipped=skipped,
                )

                for item in new_items:
                    try:
                        vault.archive_raw(
                            platform=item.platform,
                            keyword=keyword,
                            title=item.title,
                            source_url=item.source_url,
                            content=item.content,
                            tags=item.tags,
                        )
                    except Exception as e:
                        logger.warning("archive_raw_failed", url=item.source_url, error=str(e))

                noise_filter = NoiseFilter(use_llm=False)
                filtered = await noise_filter.filter_batch(new_items)
                clean = [f for f in filtered if f.verdict != NoiseVerdict.NOISE]
                task.noise_count = len([f for f in filtered if f.verdict == NoiseVerdict.NOISE])
                task.extracted_count = len(clean)
                task.filter_mode = "rule"

                for f in clean:
                    all_clean_items.append(
                        {
                            "task_id": task.id,
                            "platform": task.platform,
                            "title": f.item.title,
                            "source_url": f.item.source_url,
                            "content_preview": f.item.content[:500],
                            "approved": True,
                        }
                    )

                await crawler.close()
            except Exception as e:
                task.status = TaskStatus.FAILED
                task.error_message = str(e)[:2000]
                logger.error("crawl_failed", platform=task.platform, error=str(e))
                try:
                    await crawler.close()
                except Exception:
                    pass

        await db.commit()

    await _create_gate(run_id, GateType.MATERIAL, all_clean_items)
    await _record_phase(
        run_id,
        PhaseName.CRAWLING,
        PhaseStatus.COMPLETED,
        {
            "clean_items": len(all_clean_items),
        },
    )

    return {"clean_items": len(all_clean_items)}


async def extract_action(run_id: int, keyword: str) -> dict:
    """Extract phase: extract requirements from approved material items, create requirement gate."""
    from sqlalchemy import select

    from needradar.models.quality_gate import QualityGate as QG
    from needradar.schemas.schemas import ExtractedRequirement
    from needradar.services.vault_store import vault

    await _update_run(run_id, current_phase=PhaseName.EXTRACTING.value, status="running")
    await _record_phase(run_id, PhaseName.EXTRACTING, PhaseStatus.RUNNING)

    extracted_requirements: list[dict] = []

    async with async_session_factory() as db:
        run = await db.get(PipelineRun, run_id)
        if not run:
            return {"error": "Run not found"}

        gate_result = await db.execute(
            select(QG).where(QG.pipeline_run_id == run_id, QG.gate_type == GateType.MATERIAL.value)
        )
        material_gate = gate_result.scalar_one_or_none()

        if not material_gate or not material_gate.items_json:
            await _record_phase(run_id, PhaseName.EXTRACTING, PhaseStatus.COMPLETED, {"extracted": 0})
            await _create_gate(run_id, GateType.REQUIREMENT, [])
            return {"extracted": 0}

        items = json.loads(material_gate.items_json)
        approved_items = [i for i in items if i.get("approved", True)]

        from needradar.llm.provider import llm
        from needradar.services.analysis_service import _load_prompts

        prompts = _load_prompts()
        extraction_prompt = prompts.get("requirement_extraction", "")

        from needradar.vector import create_vector_store

        vs = create_vector_store()
        rag_retriever = None
        try:
            from needradar.services.rag_retriever import get_retriever

            rag_retriever = get_retriever()
        except Exception:
            pass

        for item_data in approved_items:
            try:
                raw_item = RawDiscussionItem(
                    platform=item_data["platform"],
                    title=item_data["title"],
                    source_url=item_data["source_url"],
                    content=item_data.get("content_preview", ""),
                    tags=[],
                )

                # RAG context
                rag_context = ""
                if rag_retriever:
                    try:
                        rag_context = await rag_retriever.retrieve_context(
                            query=f"{keyword} {raw_item.title}",
                            n_results=3,
                            min_score=0.2,
                            max_chars=1500,
                        )
                    except Exception:
                        pass

                full_prompt = extraction_prompt
                if rag_context:
                    full_prompt += "\n\n" + rag_context

                text = f"讨论标题：{raw_item.title}\n\n讨论内容：\n{raw_item.content}"
                extracted: ExtractedRequirement = await llm.extract_structured(
                    prompt=full_prompt,
                    text=text,
                    schema=ExtractedRequirement,
                )

                # Dedup via vector store
                embed_text = f"{extracted.title}\n{extracted.description}"
                results = await vs.query([embed_text], n_results=1)
                if results and results[0].score >= 0.85:
                    match_id = results[0].id
                    existing = vault.find_by_title("需求", match_id)
                    if existing:
                        meta, _ = vault.read(existing)
                        meta["提及次数"] = meta.get("提及次数", 1) + 1
                        meta.setdefault("相似来源", []).append(raw_item.source_url)
                        vault.update_frontmatter(existing, {"提及次数": meta["提及次数"], "相似来源": meta["相似来源"]})
                        continue

                # Store new requirement
                from datetime import date

                req_meta = {
                    "标题": extracted.title,
                    "来源平台": raw_item.platform,
                    "来源链接": raw_item.source_url,
                    "情感倾向": extracted.sentiment,
                    "情绪极性": extracted.emotion,
                    "提取日期": str(date.today()),
                    "关键词": keyword,
                    "置信度": extracted.confidence,
                    "提及次数": 1,
                }
                req_body = f"## 需求描述\n\n{extracted.description}\n\n## 痛点\n\n{extracted.pain_point}\n\n## 证据\n\n{extracted.evidence}\n"
                req_path = vault.write("需求", extracted.title, req_meta, req_body)

                # Add to vector store
                await vs.add(
                    ids=[extracted.title],
                    documents=[embed_text],
                    metadatas=[{"platform": raw_item.platform, "keyword": keyword}],
                )

                extracted_requirements.append(
                    {
                        "vault_path": str(req_path),
                        "title": extracted.title,
                        "sentiment": extracted.sentiment,
                        "confidence": extracted.confidence,
                        "approved": True,
                    }
                )
            except Exception as e:
                logger.warning("extract_failed", url=item_data.get("source_url"), error=str(e))

    await _create_gate(run_id, GateType.REQUIREMENT, extracted_requirements)
    await _record_phase(
        run_id,
        PhaseName.EXTRACTING,
        PhaseStatus.COMPLETED,
        {
            "extracted": len(extracted_requirements),
        },
    )

    return {"extracted": len(extracted_requirements)}


async def report_action(run_id: int, keyword: str) -> dict:
    """Report phase: generate insight report, verify, create insight gate."""
    await _update_run(run_id, current_phase=PhaseName.REPORTING.value, status="running")
    await _record_phase(run_id, PhaseName.REPORTING, PhaseStatus.RUNNING)

    report_path = None
    try:
        from needradar.services.report_service import get_report_service

        rs = get_report_service()
        report_path = await asyncio.wait_for(rs.generate_report(keyword), timeout=120)
    except asyncio.TimeoutError:
        logger.warning("report_generation_timeout", keyword=keyword)
    except Exception as e:
        logger.warning("report_generation_failed", keyword=keyword, error=str(e))

    verification_result = None
    if report_path:
        try:
            from needradar.services.content_verifier import get_verifier

            verifier = get_verifier()
            v_output = await verifier.verify_report(report_path.stem)
            verification_result = {
                "overall_score": v_output.overall_score,
                "fact_check_score": v_output.fact_check_score,
                "consistency_score": v_output.consistency_score,
                "source_reliability_score": v_output.source_reliability_score,
                "hallucination_count": v_output.hallucination_count,
                "claims_count": len(v_output.claims),
            }
        except Exception as e:
            logger.warning("verify_failed", error=str(e))

    gate_items = [
        {
            "report_path": str(report_path) if report_path else None,
            "report_title": report_path.stem if report_path else None,
            "verification": verification_result,
            "approved": True,
        }
    ]
    await _create_gate(run_id, GateType.INSIGHT, gate_items)
    await _record_phase(
        run_id,
        PhaseName.REPORTING,
        PhaseStatus.COMPLETED,
        {
            "report_path": str(report_path) if report_path else None,
            "verification": verification_result,
        },
    )

    return {"report_path": str(report_path) if report_path else None}


async def archive_action(run_id: int) -> dict:
    """Archive phase: mark tasks as completed."""
    await _record_phase(run_id, PhaseName.ARCHIVING, PhaseStatus.RUNNING)

    async with async_session_factory() as db:
        run = await db.get(PipelineRun, run_id)
        if not run:
            return {"error": "Run not found"}

        task_ids = json.loads(run.task_ids_json)
        for tid in task_ids:
            task = await db.get(CrawlTask, tid)
            if task and task.status != TaskStatus.FAILED:
                task.status = TaskStatus.COMPLETED
        await db.commit()

    await _record_phase(run_id, PhaseName.ARCHIVING, PhaseStatus.COMPLETED)
    return {"status": "done"}


async def distill_action(run_id: int) -> dict:
    """Distill phase: extract knowledge from this pipeline run."""
    await _record_phase(run_id, PhaseName.DISTILLING, PhaseStatus.RUNNING)

    try:
        async with async_session_factory() as db:
            from needradar.services.knowledge_distiller import KnowledgeDistiller

            distiller = KnowledgeDistiller(db)
            await distiller.distill_all(run_id)
    except Exception as e:
        logger.warning("distill_failed", run_id=run_id, error=str(e))

    await _record_phase(run_id, PhaseName.DISTILLING, PhaseStatus.COMPLETED)
    return {"status": "done"}


async def complete_action(run_id: int) -> dict:
    """Mark pipeline as completed."""
    await _update_run(run_id, status="completed", current_phase=PhaseName.COMPLETED.value)
    logger.info("pipeline_completed", run_id=run_id)
    return {"status": "completed"}
