from __future__ import annotations

import enum

from sqlalchemy import ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from needradar.models.base import Base, TimestampMixin


class FeedbackType(str, enum.Enum):
    ITEM_REMOVED = "item_removed"
    ITEM_EDITED = "item_edited"
    ITEM_ADDED = "item_added"
    REQUIREMENT_CORRECTED = "requirement_corrected"
    REQUIREMENT_REJECTED = "requirement_rejected"
    REPORT_EDITED = "report_edited"
    CLAIM_OVERRIDDEN = "claim_overridden"


class EntityType(str, enum.Enum):
    RAW_ITEM = "raw_item"
    REQUIREMENT = "requirement"
    REPORT_SECTION = "report_section"
    VERIFICATION_CLAIM = "verification_claim"


class FeedbackRecord(TimestampMixin, Base):
    __tablename__ = "feedback_records"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    pipeline_run_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("pipeline_runs.id"), index=True
    )
    gate_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("quality_gates.id"), index=True
    )
    feedback_type: Mapped[str] = mapped_column(String(30), nullable=False)
    entity_type: Mapped[str] = mapped_column(String(30), nullable=False)
    entity_id: Mapped[str] = mapped_column(String(500), nullable=False)  # URL, vault path, or claim text
    before_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    after_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
