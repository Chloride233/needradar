from __future__ import annotations

import enum

from sqlalchemy import ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from needradar.models.base import Base, TimestampMixin


class PhaseName(str, enum.Enum):
    CRAWLING = "crawling"
    MATERIAL_GATE = "material_gate"
    EXTRACTING = "extracting"
    REQUIREMENT_GATE = "requirement_gate"
    REPORTING = "reporting"
    INSIGHT_GATE = "insight_gate"
    ARCHIVING = "archiving"
    DISTILLING = "distilling"
    COMPLETED = "completed"
    FAILED = "failed"


class PhaseStatus(str, enum.Enum):
    PENDING = "pending"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


class PipelinePhase(TimestampMixin, Base):
    __tablename__ = "pipeline_phases"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    pipeline_run_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("pipeline_runs.id"), index=True
    )
    phase: Mapped[str] = mapped_column(String(30), nullable=False)
    status: Mapped[str] = mapped_column(
        String(20), default=PhaseStatus.PENDING.value
    )
    started_at: Mapped[str | None] = mapped_column(String(40), nullable=True)
    completed_at: Mapped[str | None] = mapped_column(String(40), nullable=True)
    result_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
