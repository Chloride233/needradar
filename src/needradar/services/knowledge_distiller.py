"""Knowledge Distiller — extracts stable insights from pipeline runs
and accumulates them as long-term knowledge.

After a pipeline run completes all quality gates, this service analyzes:
- Which platforms yielded high/low quality items (based on gate outcomes)
- Which keywords produced noise vs. signal
- Which noise patterns keep recurring
- Which extraction corrections were made

Knowledge is stored in both the DB (KnowledgeEntry) and the vault
(07-知识沉淀/) for human readability.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone

from loguru import logger
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from needradar.models.feedback import FeedbackRecord, FeedbackType
from needradar.models.knowledge import KnowledgeCategory, KnowledgeEntry
from needradar.models.quality_gate import GateType, QualityGate
from needradar.models.pipeline_run import PipelineRun


class KnowledgeDistiller:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def distill_all(self, run_id: int) -> None:
        """Run all distillation methods for a completed pipeline run."""
        run = await self._db.get(PipelineRun, run_id)
        if not run:
            return

        await self.distill_platform_quality(run_id)
        await self.distill_keyword_effectiveness(run_id)
        await self.distill_noise_patterns(run_id)
        await self.distill_extraction_rules(run_id)

        logger.info("distill_completed", run_id=run_id)

    async def distill_platform_quality(self, run_id: int) -> None:
        """Record which platforms yielded high/low quality items."""
        # Get material gate to see per-platform approval rates
        gate_result = await self._db.execute(
            select(QualityGate).where(
                QualityGate.pipeline_run_id == run_id,
                QualityGate.gate_type == GateType.MATERIAL.value,
            )
        )
        gate = gate_result.scalar_one_or_none()
        if not gate or not gate.items_json:
            return

        items = json.loads(gate.items_json)
        platform_stats: dict[str, dict] = {}
        for item in items:
            platform = item.get("platform", "unknown")
            if platform not in platform_stats:
                platform_stats[platform] = {"total": 0, "approved": 0}
            platform_stats[platform]["total"] += 1
            if item.get("approved", True):
                platform_stats[platform]["approved"] += 1

        for platform, stats in platform_stats.items():
            quality_rate = stats["approved"] / stats["total"] if stats["total"] > 0 else 0
            await self._upsert_knowledge(
                KnowledgeCategory.PLATFORM_QUALITY,
                platform,
                {"quality_rate": quality_rate, "total": stats["total"], "approved": stats["approved"]},
            )

    async def distill_keyword_effectiveness(self, run_id: int) -> None:
        """Record which keywords produced noise vs. signal."""
        run = await self._db.get(PipelineRun, run_id)
        if not run:
            return

        # Get material gate items to count noise ratio
        gate_result = await self._db.execute(
            select(QualityGate).where(
                QualityGate.pipeline_run_id == run_id,
                QualityGate.gate_type == GateType.MATERIAL.value,
            )
        )
        gate = gate_result.scalar_one_or_none()
        if not gate or not gate.items_json:
            return

        items = json.loads(gate.items_json)
        total = len(items)
        approved = sum(1 for i in items if i.get("approved", True))

        await self._upsert_knowledge(
            KnowledgeCategory.KEYWORD_EFFECTIVENESS,
            run.keyword,
            {"signal_rate": approved / total if total > 0 else 0, "total_items": total},
        )

    async def distill_noise_patterns(self, run_id: int) -> None:
        """Record noise patterns from rejected items."""
        # Get feedback records for removed items
        feedback_result = await self._db.execute(
            select(FeedbackRecord).where(
                FeedbackRecord.pipeline_run_id == run_id,
                FeedbackRecord.feedback_type == FeedbackType.ITEM_REMOVED.value,
            )
        )
        feedbacks = feedback_result.scalars().all()

        for fb in feedbacks:
            if fb.before_json:
                try:
                    before = json.loads(fb.before_json)
                    pattern = before.get("title", "")[:100]
                    if pattern:
                        await self._upsert_knowledge(
                            KnowledgeCategory.NOISE_PATTERN,
                            pattern,
                            {"entity_id": fb.entity_id, "reason": fb.reason or "human_rejected"},
                        )
                except json.JSONDecodeError:
                    pass

    async def distill_extraction_rules(self, run_id: int) -> None:
        """Record extraction corrections as rules."""
        feedback_result = await self._db.execute(
            select(FeedbackRecord).where(
                FeedbackRecord.pipeline_run_id == run_id,
                FeedbackRecord.feedback_type.in_([
                    FeedbackType.REQUIREMENT_CORRECTED.value,
                    FeedbackType.REQUIREMENT_REJECTED.value,
                ]),
            )
        )
        feedbacks = feedback_result.scalars().all()

        for fb in feedbacks:
            await self._upsert_knowledge(
                KnowledgeCategory.EXTRACTION_RULE,
                fb.entity_id,
                {
                    "feedback_type": fb.feedback_type,
                    "before": fb.before_json,
                    "after": fb.after_json,
                    "reason": fb.reason,
                },
            )

    async def _upsert_knowledge(
        self, category: KnowledgeCategory, key: str, value: dict,
    ) -> None:
        """Insert or update a knowledge entry."""
        existing_result = await self._db.execute(
            select(KnowledgeEntry).where(
                KnowledgeEntry.category == category.value,
                KnowledgeEntry.key == key,
            )
        )
        existing = existing_result.scalar_one_or_none()

        if existing:
            existing.value_json = json.dumps(value, ensure_ascii=False)
            existing.source_count += 1
            existing.confidence = min(1.0, existing.confidence + 0.05)
            existing.last_confirmed_at = datetime.now(timezone.utc)
        else:
            entry = KnowledgeEntry(
                category=category.value,
                key=key,
                value_json=json.dumps(value, ensure_ascii=False),
                confidence=0.5,
                source_count=1,
            )
            self._db.add(entry)

        await self._db.commit()

        # Also write to vault for human readability
        try:
            from needradar.services.vault_store import vault
            vault.write_knowledge(category.value, key, value)
        except Exception as e:
            logger.warning("vault_knowledge_write_failed", error=str(e))
