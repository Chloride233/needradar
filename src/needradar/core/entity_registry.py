"""Entity registry — central catalog of all NeedRadar Ontology object types.

Mirrors Palantir's ontology resource model: each entry declares the entity's
display metadata, storage backend, schema, link types, allowed actions, and
prominent properties for Object View rendering.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class EntityInfo:
    """Immutable descriptor for one entity type in the NeedRadar ontology."""

    type_name: str
    display_name: str
    display_name_en: str
    icon: str
    storage: str          # "vault" | "database"
    vault_stage: str      # vault stage name if storage == "vault", else ""
    schema_ref: str       # Pydantic schema class name (string to avoid circular imports)
    links_from: tuple[str, ...] = ()
    links_to: tuple[str, ...] = ()
    actions: tuple[str, ...] = ()
    prominent_properties: tuple[str, ...] = ()
    interfaces: tuple[str, ...] = ()


# -- Registry ---------------------------------------------------------------

ENTITY_REGISTRY: dict[str, EntityInfo] = {
    "raw_discussion": EntityInfo(
        type_name="raw_discussion",
        display_name="原始讨论", display_name_en="Raw Discussion",
        icon="📄", storage="vault", vault_stage="素材",
        schema_ref="RawDiscussionItem",
        links_from=("derived_from",),
        interfaces=("HasSource", "HasVaultPath", "HasKeyword"),
    ),
    "requirement": EntityInfo(
        type_name="requirement",
        display_name="需求", display_name_en="Requirement",
        icon="📋", storage="vault", vault_stage="需求",
        schema_ref="RequirementResponse",
        links_from=("derived_from",),
        links_to=("contains", "references"),
        actions=("mark_verified", "generate_report"),
        prominent_properties=("sentiment", "confidence", "mention_count", "source_platform"),
        interfaces=("HasSource", "HasSentiment", "HasKeyword", "HasVaultPath"),
    ),
    "opportunity": EntityInfo(
        type_name="opportunity",
        display_name="项目机会", display_name_en="Opportunity",
        icon="💼", storage="database", vault_stage="",
        schema_ref="OpportunityResponse",
        links_from=("contains",),
        links_to=("generates",),
        actions=("generate_proposal", "refresh_scores"),
        prominent_properties=("overall", "vibe_code_suitability", "demand_intensity"),
        interfaces=("HasScore", "HasKeyword", "HasStatus"),
    ),
    "proposal": EntityInfo(
        type_name="proposal",
        display_name="项目提案", display_name_en="Proposal",
        icon="📝", storage="database", vault_stage="",
        schema_ref="ProposalResponse",
        links_from=("generates",),
        actions=("view_prompt",),
        prominent_properties=("effort_estimate_hours", "status"),
        interfaces=("HasKeyword", "HasStatus", "HasVaultPath", "HasTimestamps"),
    ),
    "report": EntityInfo(
        type_name="report",
        display_name="分析报告", display_name_en="Report",
        icon="📊", storage="vault", vault_stage="初稿",
        schema_ref="ReportResponse",
        links_from=("references",),
        links_to=("verified_by",),
        actions=("verify_report",),
        prominent_properties=("keyword", "stage"),
        interfaces=("HasKeyword", "HasVaultPath"),
    ),
    "crawl_task": EntityInfo(
        type_name="crawl_task",
        display_name="爬取任务", display_name_en="Crawl Task",
        icon="🕷️", storage="database", vault_stage="",
        schema_ref="TaskResponse",
        links_from=("executed_in",),
        prominent_properties=("status", "total_items", "new_items", "platform"),
        interfaces=("HasKeyword", "HasStatus", "HasTimestamps"),
    ),
    "pipeline_run": EntityInfo(
        type_name="pipeline_run",
        display_name="管道运行", display_name_en="Pipeline Run",
        icon="⚙️", storage="database", vault_stage="",
        schema_ref="PipelineRun",
        links_to=("executed_in",),
        actions=("resume",),
        prominent_properties=("status", "keyword"),
        interfaces=("HasKeyword", "HasStatus", "HasTimestamps"),
    ),
    "verification": EntityInfo(
        type_name="verification",
        display_name="验证结果", display_name_en="Verification Result",
        icon="✅", storage="database", vault_stage="",
        schema_ref="VerificationResult",
        links_from=("verified_by",),
        actions=("submit_feedback",),
        prominent_properties=("overall_score", "hallucination_count", "status"),
        interfaces=("HasScore", "HasStatus", "HasTimestamps"),
    ),
    "trending_project": EntityInfo(
        type_name="trending_project",
        display_name="趋势项目", display_name_en="Trending Project",
        icon="📈", storage="database", vault_stage="",
        schema_ref="TrendingProject",
        prominent_properties=("stars", "forks", "language", "since"),
        interfaces=("HasTimestamps"),
    ),
}

# -- Derived lookups (computed once) -----------------------------------------

_ENTITIES_BY_STORAGE: dict[str, list[EntityInfo]] = {}
for _info in ENTITY_REGISTRY.values():
    _ENTITIES_BY_STORAGE.setdefault(_info.storage, []).append(_info)

_ENTITIES_BY_INTERFACE: dict[str, list[EntityInfo]] = {}
for _info in ENTITY_REGISTRY.values():
    for _iface in _info.interfaces:
        _ENTITIES_BY_INTERFACE.setdefault(_iface, []).append(_info)


def get_entity(type_name: str) -> EntityInfo:
    """Look up a single entity type by internal key. Raises KeyError if unknown."""
    info = ENTITY_REGISTRY.get(type_name)
    if info is None:
        raise KeyError(f"Unknown entity type: {type_name}")
    return info


def list_entities(storage: str | None = None, interface: str | None = None) -> list[EntityInfo]:
    """List entity types, optionally filtered by storage backend or interface."""
    if storage:
        return _ENTITIES_BY_STORAGE.get(storage, [])
    if interface:
        return _ENTITIES_BY_INTERFACE.get(interface, [])
    return list(ENTITY_REGISTRY.values())
