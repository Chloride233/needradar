"""Interface mixins for NeedRadar entity schemas.

Reusable shapes that mirror Palantir Ontology Interfaces. Entity types
implementing the same mixin can be handled by generic UI components and
service logic without per-type branching.
"""

from __future__ import annotations


class HasSource:
    """Entity backed by a crawled source URL."""
    source_platform: str
    source_url: str


class HasSentiment:
    """Entity with LLM sentiment/emotion analysis."""
    sentiment: str
    emotion: str
    confidence: float


class HasScore:
    """Entity with multi-dimensional scoring."""
    overall_score: float
    score_breakdown: dict


class HasVaultPath:
    """Entity stored as a Markdown file in the Obsidian vault."""
    vault_path: str
    vault_stage: str


class HasKeyword:
    """Entity tagged with a search keyword."""
    keyword: str


class HasStatus:
    """Entity with a lifecycle status."""
    status: str


class HasTimestamps:
    """Entity with created/updated timestamps."""
    created_at: str
    updated_at: str
