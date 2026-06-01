from __future__ import annotations

from enum import Enum

from sqlalchemy import String, Text
from sqlalchemy.orm import Mapped, mapped_column

from needradar.models.base import Base, TimestampMixin


class LinkType(str, Enum):
    """Semantic link types between entities in the NeedRadar ontology."""

    DERIVED_FROM = "derived_from"       # Requirement ← RawDiscussion
    CONTAINS = "contains"                # Opportunity → Requirement
    GENERATES = "generates"              # Opportunity → Proposal
    REFERENCES = "references"            # Report → Requirement
    VERIFIED_BY = "verified_by"         # Report ← VerificationResult
    EXECUTED_IN = "executed_in"         # CrawlTask → PipelineRun


class EntityLink(TimestampMixin, Base):
    """Explicit entity relationship — the foundation for Object View traversal.

    Replaces ad-hoc JSON arrays and string references with a queryable link
    graph.  Each row is a directed edge: ``source --[link_type]--> target``.
    """

    __tablename__ = "entity_links"

    id: Mapped[int] = mapped_column(primary_key=True)

    source_type: Mapped[str] = mapped_column(
        String(50), index=True, comment="Entity type of the source node"
    )
    source_id: Mapped[str] = mapped_column(
        String(500), index=True, comment="Identifier (vault path or DB primary key)"
    )

    link_type: Mapped[str] = mapped_column(
        String(50), index=True, comment="Semantic relationship type"
    )

    target_type: Mapped[str] = mapped_column(
        String(50), index=True, comment="Entity type of the target node"
    )
    target_id: Mapped[str] = mapped_column(
        String(500), index=True, comment="Identifier (vault path or DB primary key)"
    )

    metadata_json: Mapped[str] = mapped_column(
        Text, default="{}", comment="Optional relationship metadata (confidence, context, etc.)"
    )
