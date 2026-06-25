"""Pipeline Orchestrator — state-machine-based pipeline with quality gates.

Transforms the monolithic fire-and-forget pipeline into a phase-based
orchestrator that pauses at 3 quality gates for human review:

  crawl -> GATE_1 (material) -> extract -> GATE_2 (requirement)
  -> report+verify -> GATE_3 (insight) -> archive+distill -> done

Each gate supports approve/reject/edit. Pipeline cannot proceed without
human approval at each gate.
"""

from __future__ import annotations

import asyncio
import json
from datetime import datetime, timezone

from loguru import logger
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from needradar.core.database import async_session_factory
from needradar.models.crawl_task import CrawlTask, TaskStatus
from needradar.models.feedback import FeedbackRecord, FeedbackType
from needradar.models.knowledge import KnowledgeCategory, KnowledgeEntry
from needradar.models.pipeline_phase import PhaseName, PhaseStatus, PipelinePhase
from needradar.models.pipeline_run import PipelineRun
from needradar.models.quality_gate import GateStatus, GateType, QualityGate
from needradar.schemas.schemas import NoiseVerdict, RawDiscussionItem


class PipelineOrchestrator:
    """Manages pipeline execution as a state machine with quality gates."""

    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    # ── Public API ──

    async def start(self, keyword: str, platforms: list[str]) -> PipelineRun:
        """Create a new agent-mode pipeline run and begin the crawling phase."""
        run = PipelineRun(
            keyword=keyword,
            status="running",
            task_ids_json="[]",
            stages_json="[]",
            is_agent_mode=True,
            current_phase=PhaseName.CRAWLING.value,
            gate_status="none",
        )
        self._db.add(run)
        await self._db.flush()

        # Create CrawlTask rows for each platform
        task_ids: list[int] = []
        for platform in platforms:
            task = CrawlTask(keyword=keyword, platform=platform, status=TaskStatus.PENDING)
            self._db.add(task)
            await self._db.flush()
            task_ids.append(task.id)
        run.task_ids_json = json.dumps(task_ids)
        await self._db.commit()

        # Start crawling in background
        asyncio.create_task(self._run_from_phase(run.id, PhaseName.CRAWLING))
        return run

    async def resume_after_gate(
        self,
        gate_id: int,
        decision: str,
        edits: list[dict] | None = None,
        note: str = "",
    ) -> None:
        """Process a human gate decision and advance the pipeline."""
        gate = await self._db.get(QualityGate, gate_id)
        if not gate:
            raise ValueError(f"Gate {gate_id} not found")
        if gate.status != GateStatus.AWAITING_REVIEW.value:
            raise ValueError(f"Gate {gate_id} is not awaiting review (status={gate.status})")

        run = await self._db.get(PipelineRun, gate.pipeline_run_id)
        if not run:
            raise ValueError(f"PipelineRun {gate.pipeline_run_id} not found")

        # Validate decision
        valid_decisions = {"approve", "reject", "edit"}
        if decision not in valid_decisions:
            raise ValueError(f"Invalid decision '{decision}'. Must be one of: {valid_decisions}")

        gate.human_decision = decision
        gate.reviewer_note = note
        gate.reviewed_at = datetime.now(timezone.utc).isoformat()

        if decision == "reject":
            gate.status = GateStatus.REJECTED.value
            run.status = "rejected"
            run.gate_status = "rejected"
            await self._db.commit()
            return

        # "approve" and "edit" both mean approve; "edit" includes corrections
        gate.status = GateStatus.APPROVED.value
        if edits:
            await self._record_edits(gate, edits)
        await self._apply_gate_edits(run, gate, edits or [])

        run.gate_status = "approved"
        await self._db.commit()

        # Advance to next phase
        next_phase = self._get_next_phase(GateType(gate.gate_type))
        if next_phase:
            asyncio.create_task(self._run_from_phase(run.id, next_phase))

    async def get_gate_items(self, gate_id: int) -> list[dict]:
        """Retrieve the items under review for a gate."""
        gate = await self._db.get(QualityGate, gate_id)
        if not gate:
            raise ValueError(f"Gate {gate_id} not found")
        if gate.items_json:
            return json.loads(gate.items_json)
        return []

    # ── Internal Phase Execution ──

    async def _run_from_phase(self, run_id: int, phase: PhaseName) -> None:
        """Resume pipeline from a given phase.

        IMPORTANT: Opens its own DB session. Background tasks MUST NOT
        use the request-scoped session from the API handler.
        """
        async with async_session_factory() as db:
            run = await db.get(PipelineRun, run_id)
            if not run:
                return

            try:
                if phase == PhaseName.CRAWLING:
                    await self._phase_crawl(run, db)
                elif phase == PhaseName.EXTRACTING:
                    await self._phase_extract(run, db)
                elif phase == PhaseName.REPORTING:
                    await self._phase_report(run, db)
                elif phase == PhaseName.ARCHIVING:
                    await self._phase_archive(run, db)
                elif phase == PhaseName.DISTILLING:
                    await self._phase_distill(run, db)
                elif phase == PhaseName.COMPLETED:
                    run.status = "completed"
                    run.current_phase = PhaseName.COMPLETED.value
                    await db.commit()
                    logger.info("pipeline_completed", run_id=run_id)
            except Exception as e:
                run.status = "failed"
                run.error_message = str(e)[:2000]
                run.current_phase = PhaseName.FAILED.value
                await db.commit()
                logger.error("pipeline_phase_failed", run_id=run_id, phase=phase.value, error=str(e))

    async def _phase_crawl(self, run: PipelineRun, db: AsyncSession) -> None:
        """Execute crawl phase, then create material gate."""
        await self._record_phase(run, PhaseName.CRAWLING, PhaseStatus.RUNNING, db=db)

        from needradar.crawlers.factory import create_crawler
        from needradar.services.noise_filter import NoiseFilter
        from needradar.services.vault_store import vault

        keyword = run.keyword
        task_ids = json.loads(run.task_ids_json)
        tasks = []
        for tid in task_ids:
            task = await db.get(CrawlTask, tid)
            if task:
                tasks.append(task)

        all_clean_items: list[dict] = []

        for task in tasks:
            crawler = create_crawler(task.platform)
            try:
                task.status = TaskStatus.RUNNING
                await db.commit()

                raw_items = await asyncio.wait_for(
                    crawler.crawl(keyword), timeout=30 * 60
                )
                task.total_items = len(raw_items)

                # Incremental filter
                from needradar.models.fingerprint import CrawlFingerprint
                known_result = await db.execute(
                    select(CrawlFingerprint.source_url).where(
                        CrawlFingerprint.keyword == keyword,
                        CrawlFingerprint.platform == task.platform,
                    )
                )
                known = {row[0] for row in known_result.all()}
                new_items = [item for item in raw_items if item.source_url not in known]
                task.new_items = len(new_items)
                task.skipped_items = len(raw_items) - len(new_items)

                # Save fingerprints
                for item in new_items:
                    db.add(CrawlFingerprint(
                        keyword=keyword, platform=task.platform, source_url=item.source_url,
                    ))

                # Archive raw to vault
                for item in new_items:
                    try:
                        vault.archive_raw(
                            platform=item.platform, keyword=keyword,
                            title=item.title, source_url=item.source_url,
                            content=item.content, tags=item.tags,
                        )
                    except Exception as e:
                        logger.warning("archive_raw_failed", url=item.source_url, error=str(e))

                # Noise filter
                noise_filter = NoiseFilter(use_llm=False)
                filtered = await noise_filter.filter_batch(new_items)
                clean = [f for f in filtered if f.verdict != NoiseVerdict.NOISE]
                task.noise_count = len([f for f in filtered if f.verdict == NoiseVerdict.NOISE])
                task.extracted_count = len(clean)
                task.filter_mode = "rule"

                # Collect items for gate review
                for f in clean:
                    all_clean_items.append({
                        "task_id": task.id,
                        "platform": task.platform,
                        "title": f.item.title,
                        "source_url": f.item.source_url,
                        "content_preview": f.item.content[:500],
                        "approved": True,  # default: approve all
                    })

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

        # Create material gate
        await self._create_gate(run, GateType.MATERIAL, all_clean_items, db=db)
        await self._record_phase(run, PhaseName.CRAWLING, PhaseStatus.COMPLETED, {
            "total_items": sum(t.total_items or 0 for t in tasks),
            "new_items": sum(t.new_items or 0 for t in tasks),
            "clean_items": len(all_clean_items),
        }, db=db)

    async def _phase_extract(self, run: PipelineRun, db: AsyncSession) -> None:
        """Execute extraction phase on approved items, then create requirement gate."""
        await self._record_phase(run, PhaseName.EXTRACTING, PhaseStatus.RUNNING, db=db)

        # Find the material gate and get approved items
        gate_result = await db.execute(
            select(QualityGate).where(
                QualityGate.pipeline_run_id == run.id,
                QualityGate.gate_type == GateType.MATERIAL.value,
            )
        )
        material_gate = gate_result.scalar_one_or_none()
        if not material_gate or not material_gate.items_json:
            await self._record_phase(run, PhaseName.EXTRACTING, PhaseStatus.COMPLETED, {"extracted": 0}, db=db)
            return

        items = json.loads(material_gate.items_json)
        approved_items = [i for i in items if i.get("approved", True)]

        # Extract each approved item
        extracted_requirements: list[dict] = []
        for item_data in approved_items:
            try:
                # Reconstruct RawDiscussionItem for extraction
                raw_item = RawDiscussionItem(
                    platform=item_data["platform"],
                    title=item_data["title"],
                    source_url=item_data["source_url"],
                    content=item_data.get("content_preview", ""),
                    tags=[],
                )
                req_path = await self._extract_single(run.keyword, raw_item, db=db)
                if req_path:
                    from needradar.services.vault_store import vault
                    meta, body = vault.read(req_path)
                    extracted_requirements.append({
                        "vault_path": str(req_path),
                        "title": meta.get("标题", ""),
                        "sentiment": meta.get("情感倾向", ""),
                        "emotion": meta.get("情绪极性", ""),
                        "confidence": meta.get("置信度", 0.0),
                        "pain_point": "",  # extracted from body
                        "approved": True,
                    })
            except Exception as e:
                logger.warning("extract_failed", url=item_data.get("source_url"), error=str(e))

        # Create requirement gate
        await self._create_gate(run, GateType.REQUIREMENT, extracted_requirements, db=db)
        await self._record_phase(run, PhaseName.EXTRACTING, PhaseStatus.COMPLETED, {
            "extracted": len(extracted_requirements),
        }, db=db)

    async def _phase_report(self, run: PipelineRun, db: AsyncSession) -> None:
        """Execute report generation and verification, then create insight gate."""
        await self._record_phase(run, PhaseName.REPORTING, PhaseStatus.RUNNING, db=db)

        # Generate report
        from needradar.services.report_service import get_report_service
        rs = get_report_service()
        report_path = await rs.generate_report(run.keyword)

        # Verify report
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

        # Create insight gate
        gate_items = [{
            "report_path": str(report_path) if report_path else None,
            "report_title": report_path.stem if report_path else None,
            "verification": verification_result,
            "approved": True,
        }]
        await self._create_gate(run, GateType.INSIGHT, gate_items, db=db)
        await self._record_phase(run, PhaseName.REPORTING, PhaseStatus.COMPLETED, {
            "report_path": str(report_path) if report_path else None,
            "verification": verification_result,
        }, db=db)

    async def _phase_archive(self, run: PipelineRun, db: AsyncSession) -> None:
        """Archive completed tasks."""
        await self._record_phase(run, PhaseName.ARCHIVING, PhaseStatus.RUNNING, db=db)
        # Mark tasks as completed
        task_ids = json.loads(run.task_ids_json)
        for tid in task_ids:
            task = await db.get(CrawlTask, tid)
            if task and task.status != TaskStatus.FAILED:
                task.status = TaskStatus.COMPLETED
        await db.commit()
        await self._record_phase(run, PhaseName.ARCHIVING, PhaseStatus.COMPLETED, db=db)

    async def _phase_distill(self, run: PipelineRun, db: AsyncSession) -> None:
        """Distill knowledge from this pipeline run."""
        await self._record_phase(run, PhaseName.DISTILLING, PhaseStatus.RUNNING, db=db)

        try:
            from needradar.services.knowledge_distiller import KnowledgeDistiller
            distiller = KnowledgeDistiller(db)
            await distiller.distill_all(run.id)
        except Exception as e:
            logger.warning("distill_failed", run_id=run.id, error=str(e))

        await self._record_phase(run, PhaseName.DISTILLING, PhaseStatus.COMPLETED, db=db)

    # ── Helpers ──

    async def _extract_single(self, keyword: str, item: RawDiscussionItem, db: AsyncSession | None = None):
        """Extract a single requirement from a raw item."""
        from needradar.services.analysis_service import AnalysisService
        svc = AnalysisService(db or self._db)
        return await svc._extract_and_store(keyword, item)

    async def _create_gate(self, run: PipelineRun, gate_type: GateType, items: list[dict], db: AsyncSession | None = None) -> QualityGate:
        """Create a quality gate and pause the pipeline."""
        _db = db or self._db
        gate = QualityGate(
            pipeline_run_id=run.id,
            gate_type=gate_type.value,
            status=GateStatus.AWAITING_REVIEW.value,
            items_json=json.dumps(items, ensure_ascii=False),
            items_count=len(items),
        )
        _db.add(gate)
        run.current_phase = f"{gate_type.value}_gate"
        run.gate_status = "awaiting_review"
        run.status = "paused"
        await _db.commit()
        logger.info("gate_created", run_id=run.id, gate_type=gate_type.value, items=len(items))
        return gate

    async def _record_phase(
        self, run: PipelineRun, phase: PhaseName, status: PhaseStatus, result: dict | None = None,
        db: AsyncSession | None = None,
    ) -> PipelinePhase:
        """Record a pipeline phase execution."""
        _db = db or self._db
        phase_record = PipelinePhase(
            pipeline_run_id=run.id,
            phase=phase.value,
            status=status.value,
            started_at=datetime.now(timezone.utc).isoformat() if status == PhaseStatus.RUNNING else None,
            completed_at=datetime.now(timezone.utc).isoformat() if status in (PhaseStatus.COMPLETED, PhaseStatus.FAILED) else None,
            result_json=json.dumps(result, ensure_ascii=False) if result else None,
        )
        _db.add(phase_record)
        await _db.commit()
        return phase_record

    async def _record_edits(self, gate: QualityGate, edits: list[dict]) -> None:
        """Record human edits as structured feedback."""
        for edit in edits:
            feedback = FeedbackRecord(
                pipeline_run_id=gate.pipeline_run_id,
                gate_id=gate.id,
                feedback_type=edit.get("feedback_type", "item_edited"),
                entity_type=edit.get("entity_type", "raw_item"),
                entity_id=edit.get("entity_id", ""),
                before_json=json.dumps(edit.get("before"), ensure_ascii=False) if edit.get("before") else None,
                after_json=json.dumps(edit.get("after"), ensure_ascii=False) if edit.get("after") else None,
                reason=edit.get("reason"),
            )
            self._db.add(feedback)
        await self._db.commit()

    async def _apply_gate_edits(self, run: PipelineRun, gate: QualityGate, edits: list[dict]) -> None:
        """Apply gate edits: promote approved items, handle rejections."""
        if gate.gate_type == GateType.REQUIREMENT.value:
            # Promote approved requirements from staging to final vault
            items = json.loads(gate.items_json) if gate.items_json else []
            from needradar.services.vault_store import vault
            for item in items:
                if item.get("approved", True) and item.get("vault_path"):
                    # Requirements are already in the final vault location
                    pass

    def _get_next_phase(self, gate_type: GateType) -> PhaseName | None:
        """Get the next phase after a gate is approved."""
        mapping = {
            GateType.MATERIAL: PhaseName.EXTRACTING,
            GateType.REQUIREMENT: PhaseName.REPORTING,
            GateType.INSIGHT: PhaseName.ARCHIVING,
        }
        return mapping.get(gate_type)


def get_orchestrator(db: AsyncSession) -> PipelineOrchestrator:
    return PipelineOrchestrator(db)
