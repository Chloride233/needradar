from __future__ import annotations

from sqlalchemy import ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from needradar.models.base import Base, TimestampMixin


class ProjectProposal(TimestampMixin, Base):
    __tablename__ = "project_proposals"

    id: Mapped[int] = mapped_column(primary_key=True)
    opportunity_id: Mapped[int | None] = mapped_column(
        ForeignKey("project_opportunities.id"), nullable=True
    )
    keyword: Mapped[str] = mapped_column(String(200), index=True)
    title: Mapped[str] = mapped_column(String(300))

    problem_statement: Mapped[str] = mapped_column(Text, default="")
    target_user: Mapped[str] = mapped_column(Text, default="")
    mvp_scope_json: Mapped[str] = mapped_column(Text, default="[]")
    suggested_stack_json: Mapped[str] = mapped_column(Text, default="{}")
    effort_estimate_hours: Mapped[int] = mapped_column(Integer, default=0)
    effort_breakdown_json: Mapped[str] = mapped_column(Text, default="{}")
    traction_signals_json: Mapped[str] = mapped_column(Text, default="[]")
    claude_prompt: Mapped[str] = mapped_column(Text, default="")
    risks_json: Mapped[str] = mapped_column(Text, default="[]")

    status: Mapped[str] = mapped_column(String(30), default="draft")
    vault_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
