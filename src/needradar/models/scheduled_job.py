from __future__ import annotations

import enum

from sqlalchemy import Enum as SAEnum
from sqlalchemy import Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from needradar.models.base import Base, TimestampMixin


class JobStatus(str, enum.Enum):
    ACTIVE = "active"
    PAUSED = "paused"


class ScheduledJob(TimestampMixin, Base):
    __tablename__ = "scheduled_jobs"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(200))
    keyword: Mapped[str] = mapped_column(String(200), index=True)
    platforms: Mapped[str] = mapped_column(Text)  # JSON list
    interval_minutes: Mapped[int] = mapped_column(Integer, default=60)
    status: Mapped[JobStatus] = mapped_column(
        SAEnum(JobStatus), default=JobStatus.ACTIVE, index=True
    )
    last_run_at: Mapped[str | None] = mapped_column(Text, nullable=True)
    last_task_ids: Mapped[str | None] = mapped_column(Text, nullable=True)  # JSON list
    run_count: Mapped[int] = mapped_column(Integer, default=0)
