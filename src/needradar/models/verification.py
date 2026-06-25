from __future__ import annotations

import datetime
import enum

from sqlalchemy import DateTime, Float, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from needradar.models.base import Base, TimestampMixin


class VerificationStatus(str, enum.Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class VerificationResult(TimestampMixin, Base):
    __tablename__ = "verification_results"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    report_title: Mapped[str] = mapped_column(String(200), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(20), default=VerificationStatus.PENDING)
    overall_score: Mapped[float | None] = mapped_column(Float, nullable=True)  # 0-100
    fact_check_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    consistency_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    source_reliability_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    total_claims: Mapped[int] = mapped_column(Integer, default=0)
    hallucination_count: Mapped[int] = mapped_column(Integer, default=0)
    flagged_count: Mapped[int] = mapped_column(Integer, default=0)
    claims_json: Mapped[str | None] = mapped_column(Text, nullable=True)  # JSON array of claims
    suggestions_json: Mapped[str | None] = mapped_column(Text, nullable=True)  # correction suggestions
    reviewer_note: Mapped[str | None] = mapped_column(Text, nullable=True)  # human feedback
    verdict_override: Mapped[str | None] = mapped_column(String(50), nullable=True)  # manual verdict override
    reviewed_at: Mapped[datetime.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
