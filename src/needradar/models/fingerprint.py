from __future__ import annotations

from sqlalchemy import Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from needradar.models.base import Base


class CrawlFingerprint(Base):
    __tablename__ = "crawl_fingerprints"
    __table_args__ = (
        Index("ix_fp_keyword_platform", "keyword", "platform"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    keyword: Mapped[str] = mapped_column(String(200), index=True)
    platform: Mapped[str] = mapped_column(String(50))
    source_url: Mapped[str] = mapped_column(Text)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=True)
