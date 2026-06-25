from __future__ import annotations

from sqlalchemy import Boolean, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from needradar.models.base import Base, TimestampMixin


class PipelineRun(TimestampMixin, Base):
    __tablename__ = "pipeline_runs"

    id: Mapped[int] = mapped_column(primary_key=True)
    keyword: Mapped[str] = mapped_column(String(200), index=True)
    status: Mapped[str] = mapped_column(String(30), default="pending")
    stages_json: Mapped[str] = mapped_column(Text, default="[]")
    task_ids_json: Mapped[str] = mapped_column(Text, default="[]")
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Agent mode fields
    current_phase: Mapped[str | None] = mapped_column(String(30), nullable=True)
    gate_status: Mapped[str] = mapped_column(String(20), default="none")
    is_agent_mode: Mapped[bool] = mapped_column(Boolean, default=False)
