from __future__ import annotations

from sqlalchemy import String, Text
from sqlalchemy.orm import Mapped, mapped_column

from needradar.models.base import Base, TimestampMixin


class ProjectOpportunity(TimestampMixin, Base):
    __tablename__ = "project_opportunities"

    id: Mapped[int] = mapped_column(primary_key=True)
    keyword: Mapped[str] = mapped_column(String(200), index=True)
    title: Mapped[str] = mapped_column(String(300))
    description: Mapped[str] = mapped_column(Text, default="")

    scores_json: Mapped[str] = mapped_column(Text, default="{}")
    traction_json: Mapped[str] = mapped_column(Text, default="{}")
    source_req_ids_json: Mapped[str] = mapped_column(Text, default="[]")

    status: Mapped[str] = mapped_column(String(30), default="pending")
