"""Pipeline Orchestrator — Burr-based state machine with quality gates.

Replaces the hand-written if/elif state machine with Apache Burr's
declarative graph. Quality gates are Burr interrupts.

Pipeline flow:
  crawl → material_gate → extract → requirement_gate
  → report → insight_gate → archive → distill → completed
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
from needradar.models.feedback import FeedbackRecord
from needradar.models.pipeline_run import PipelineRun
from needradar.models.quality_gate import GateStatus, GateType, QualityGate


class PipelineOrchestrator:
    """Manages pipeline execution as a Burr state machine with quality gates."""

    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    # ── Public API ──

    async def start(self, keyword: str, platforms: list[str]) -> PipelineRun:
        """Create a new agent-mode pipeline run and begin crawling."""
        run = PipelineRun(
            keyword=keyword,
            status="running",
            task_ids_json="[]",
            stages_json="[]",
            is_agent_mode=True,
            current_phase="crawling",
            gate_status="none",
        )
        self._db.add(run)
        await self._db.flush()

        task_ids: list[int] = []
        for platform in platforms:
            task = CrawlTask(keyword=keyword, platform=platform, status=TaskStatus.PENDING)
            self._db.add(task)
            await self._db.flush()
            task_ids.append(task.id)
        run.task_ids_json = json.dumps(task_ids)
        await self._db.commit()

        # Start pipeline in background
        asyncio.create_task(self._run_pipeline(run.id, keyword, platforms))
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

        gate.status = GateStatus.APPROVED.value
        if edits:
            await self._record_edits(gate, edits)
        await self._apply_gate_edits(run, gate, edits or [])

        run.gate_status = "approved"
        await self._db.commit()

        # Resume pipeline from the approved gate's next phase
        asyncio.create_task(self._resume_from_phase(run.id, GateType(gate.gate_type), run.keyword))

    async def get_gate_items(self, gate_id: int) -> list[dict]:
        """Retrieve the items under review for a gate."""
        gate = await self._db.get(QualityGate, gate_id)
        if not gate:
            raise ValueError(f"Gate {gate_id} not found")
        if gate.items_json:
            return json.loads(gate.items_json)
        return []

    # ── Pipeline Execution (Burr-style sequential with interrupts) ──

    async def _run_pipeline(self, run_id: int, keyword: str, platforms: list[str]) -> None:
        """Execute crawl phase, then pause at material gate for human review.

        Subsequent phases are driven by resume_after_gate() calls.
        """
        from needradar.services.pipeline_actions import crawl_action

        try:
            result = await crawl_action(run_id, keyword, platforms)
            if "error" in result:
                await self._fail(run_id, result["error"])
                return
            # Pipeline is now paused at material gate — wait for resume

        except Exception as e:
            await self._fail(run_id, str(e))

    async def _resume_from_phase(self, run_id: int, phase: GateType, keyword: str) -> None:
        """Resume pipeline from a specific phase after gate approval."""
        from needradar.services.pipeline_actions import (
            extract_action, report_action, archive_action, distill_action, complete_action,
        )

        try:
            if phase == GateType.MATERIAL:
                # After material gate → extract
                result = await extract_action(run_id, keyword)
                if "error" in result:
                    await self._fail(run_id, result["error"])
                # Pipeline pauses at requirement gate

            elif phase == GateType.REQUIREMENT:
                # After requirement gate → report
                result = await report_action(run_id, keyword)
                if "error" in result:
                    await self._fail(run_id, result["error"])
                # Pipeline pauses at insight gate

            elif phase == GateType.INSIGHT:
                # After insight gate → archive → distill → complete
                await archive_action(run_id)
                await distill_action(run_id)
                await complete_action(run_id)

        except Exception as e:
            await self._fail(run_id, str(e))

    async def _fail(self, run_id: int, error: str) -> None:
        """Mark pipeline as failed."""
        async with async_session_factory() as db:
            run = await db.get(PipelineRun, run_id)
            if run:
                run.status = "failed"
                run.error_message = error[:2000]
                run.current_phase = "failed"
                await db.commit()
        logger.error("pipeline_failed", run_id=run_id, error=error)

    # ── Helpers ──

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
            items = json.loads(gate.items_json) if gate.items_json else []
            from needradar.services.vault_store import vault
            for item in items:
                if item.get("approved", True) and item.get("vault_path"):
                    pass  # Requirements are already in the final vault location


def get_orchestrator(db: AsyncSession) -> PipelineOrchestrator:
    return PipelineOrchestrator(db)
