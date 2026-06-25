from __future__ import annotations

import enum

from sqlalchemy import DateTime, Float, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from needradar.models.base import Base, TimestampMixin


class KnowledgeCategory(str, enum.Enum):
    PLATFORM_QUALITY = "platform_quality"
    KEYWORD_EFFECTIVENESS = "keyword_effectiveness"
    NOISE_PATTERN = "noise_pattern"
    EXTRACTION_RULE = "extraction_rule"
    PROMPT_PATTERN = "prompt_pattern"


class KnowledgeEntry(TimestampMixin, Base):
    __tablename__ = "knowledge_entries"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    category: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    key: Mapped[str] = mapped_column(String(200), nullable=False, index=True)
    value_json: Mapped[str] = mapped_column(Text, nullable=False)
    confidence: Mapped[float] = mapped_column(Float, default=0.5)
    source_count: Mapped[int] = mapped_column(Integer, default=1)
    last_confirmed_at: Mapped[str | None] = mapped_column(
        DateTime(timezone=True), nullable=True, server_default=func.now()
    )
