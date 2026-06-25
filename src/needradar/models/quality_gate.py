from __future__ import annotations

import enum

from sqlalchemy import ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from needradar.models.base import Base, TimestampMixin


class GateType(str, enum.Enum):
    MATERIAL = "material"  # post-crawl: review raw items
    REQUIREMENT = "requirement"  # post-extraction: review extracted requirements
    INSIGHT = "insight"  # post-report: review report + verification


class GateStatus(str, enum.Enum):
    PENDING = "pending"
    AWAITING_REVIEW = "awaiting_review"
    APPROVED = "approved"
    REJECTED = "rejected"
    EDITING = "editing"


class QualityGate(TimestampMixin, Base):
    __tablename__ = "quality_gates"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    pipeline_run_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("pipeline_runs.id"), index=True
    )
    gate_type: Mapped[str] = mapped_column(String(20), nullable=False)
    status: Mapped[str] = mapped_column(
        String(20), default=GateStatus.PENDING.value
    )
    items_json: Mapped[str | None] = mapped_column(Text, nullable=True)  # items under review
    items_count: Mapped[int] = mapped_column(Integer, default=0)
    human_decision: Mapped[str | None] = mapped_column(String(20), nullable=True)
    human_edits_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    reviewer_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    reviewed_at: Mapped[str | None] = mapped_column(String(40), nullable=True)
