"""Feedback Service — records structured human corrections from quality gates
and derives test cases for prompt optimization.

This closes the loop: human edits at gates → structured FeedbackRecord →
test cases for PromptOptimizer → improved prompts → better extraction.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone

from loguru import logger
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from needradar.models.feedback import EntityType, FeedbackRecord, FeedbackType
from needradar.models.quality_gate import GateType, QualityGate


class FeedbackService:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    # ── Record feedback ──

    async def record_correction(
        self,
        gate_id: int,
        pipeline_run_id: int,
        feedback_type: FeedbackType,
        entity_type: EntityType,
        entity_id: str,
        before: dict | None = None,
        after: dict | None = None,
        reason: str | None = None,
    ) -> FeedbackRecord:
        """Record a single human correction."""
        record = FeedbackRecord(
            pipeline_run_id=pipeline_run_id,
            gate_id=gate_id,
            feedback_type=feedback_type.value,
            entity_type=entity_type.value,
            entity_id=entity_id,
            before_json=json.dumps(before, ensure_ascii=False) if before else None,
            after_json=json.dumps(after, ensure_ascii=False) if after else None,
            reason=reason,
        )
        self._db.add(record)
        await self._db.commit()
        await self._db.refresh(record)
        logger.info(
            "feedback_recorded",
            gate_id=gate_id,
            feedback_type=feedback_type.value,
            entity_type=entity_type.value,
        )
        return record

    async def record_gate_edits(
        self,
        gate_id: int,
        pipeline_run_id: int,
        edits: list[dict],
    ) -> list[FeedbackRecord]:
        """Record multiple edits from a gate review."""
        records = []
        for edit in edits:
            ft = edit.get("feedback_type", "item_edited")
            et = edit.get("entity_type", "raw_item")
            record = await self.record_correction(
                gate_id=gate_id,
                pipeline_run_id=pipeline_run_id,
                feedback_type=FeedbackType(ft),
                entity_type=EntityType(et),
                entity_id=edit.get("entity_id", ""),
                before=edit.get("before"),
                after=edit.get("after"),
                reason=edit.get("reason"),
            )
            records.append(record)
        return records

    # ── Query feedback ──

    async def get_extraction_corrections(
        self, keyword: str | None = None, limit: int = 50,
    ) -> list[FeedbackRecord]:
        """Get corrections related to requirement extraction."""
        stmt = (
            select(FeedbackRecord)
            .where(FeedbackRecord.feedback_type.in_([
                FeedbackType.REQUIREMENT_CORRECTED.value,
                FeedbackType.REQUIREMENT_REJECTED.value,
            ]))
            .order_by(FeedbackRecord.created_at.desc())
            .limit(limit)
        )
        result = await self._db.execute(stmt)
        return list(result.scalars().all())

    async def get_noise_corrections(self, limit: int = 50) -> list[FeedbackRecord]:
        """Get corrections related to noise filter (items removed/added)."""
        stmt = (
            select(FeedbackRecord)
            .where(FeedbackRecord.feedback_type.in_([
                FeedbackType.ITEM_REMOVED.value,
                FeedbackType.ITEM_ADDED.value,
            ]))
            .order_by(FeedbackRecord.created_at.desc())
            .limit(limit)
        )
        result = await self._db.execute(stmt)
        return list(result.scalars().all())

    async def get_all_feedback(
        self, pipeline_run_id: int | None = None, limit: int = 100,
    ) -> list[FeedbackRecord]:
        """Get all feedback, optionally filtered by pipeline run."""
        stmt = select(FeedbackRecord).order_by(FeedbackRecord.created_at.desc())
        if pipeline_run_id:
            stmt = stmt.where(FeedbackRecord.pipeline_run_id == pipeline_run_id)
        stmt = stmt.limit(limit)
        result = await self._db.execute(stmt)
        return list(result.scalars().all())

    # ── Derive test cases ──

    async def derive_test_cases_from_feedback(
        self, min_corrections: int = 1,
    ) -> list[dict]:
        """Generate test cases from accumulated human corrections.

        Each correction where a human changed the extracted requirement
        becomes a test case: the original discussion text is the input,
        and the human-corrected extraction is the expected output.

        Returns test cases in the same format as prompt_test_cases.yaml.
        """
        corrections = await self.get_extraction_corrections(limit=200)
        if len(corrections) < min_corrections:
            logger.info("not_enough_feedback", got=len(corrections), need=min_corrections)
            return []

        test_cases = []
        for i, corr in enumerate(corrections):
            before = json.loads(corr.before_json) if corr.before_json else {}
            after = json.loads(corr.after_json) if corr.after_json else {}

            if not before or not after:
                continue

            # Build test case from before/after
            test_case = self._correction_to_test_case(i, corr, before, after)
            if test_case:
                test_cases.append(test_case)

        logger.info("derived_test_cases", count=len(test_cases), from_corrections=len(corrections))
        return test_cases

    def _correction_to_test_case(
        self, index: int, corr: FeedbackRecord, before: dict, after: dict,
    ) -> dict | None:
        """Convert a single correction into a test case dict."""
        # The "before" is what the LLM extracted
        # The "after" is what the human corrected it to
        # We use the original discussion as input (from entity_id or before)
        input_title = before.get("title", after.get("title", ""))
        input_content = before.get("description", after.get("description", ""))

        if not input_title:
            return None

        # Build expected from the human-corrected version
        expected = {}
        if "sentiment" in after:
            expected["sentiment"] = after["sentiment"]
        elif "sentiment" in before:
            expected["sentiment"] = before["sentiment"]

        if "emotion" in after:
            expected["emotion"] = after["emotion"]
        elif "emotion" in before:
            expected["emotion"] = before["emotion"]

        if "confidence" in after:
            conf = after["confidence"]
            expected["confidence_min"] = max(0.0, conf - 0.1)
            expected["confidence_max"] = min(1.0, conf + 0.1)

        if "title" in after:
            # Extract keywords from the corrected title
            title_keywords = [w for w in after["title"].split() if len(w) > 1]
            expected["title_keywords"] = title_keywords[:5]

        if not expected:
            return None

        return {
            "id": f"feedback_{corr.id}_{index}",
            "input": {
                "title": input_title,
                "content": input_content,
                "platform": before.get("platform", "unknown"),
            },
            "expected": expected,
            "_source": {
                "feedback_id": corr.id,
                "feedback_type": corr.feedback_type,
                "reason": corr.reason,
            },
        }
