"""Tests for schema mixins and entity registry."""

from __future__ import annotations

import pytest

from needradar.core.entity_registry import (
    ENTITY_REGISTRY,
    EntityInfo,
    get_entity,
    list_entities,
)
from needradar.schemas.mixins import (
    HasKeyword,
    HasSentiment,
    HasSource,
)
from needradar.schemas.schemas import RequirementResponse


class TestMixins:
    def test_requirement_inherits_from_mixins(self):
        """RequirementResponse subclasses HasSource, HasSentiment, HasKeyword."""
        assert issubclass(RequirementResponse, HasSource)
        assert issubclass(RequirementResponse, HasSentiment)
        assert issubclass(RequirementResponse, HasKeyword)

    def test_instance_passes_isinstance_checks(self):
        """A RequirementResponse instance passes isinstance checks for all mixins."""
        req = RequirementResponse(
            title="离线编辑", description="需要离线编辑功能",
            source_platform="github", source_url="https://github.com/issue/1",
            sentiment="strong", emotion="negative", confidence=0.92,
            mention_count=8, keyword="notion",
        )
        assert isinstance(req, HasSource)
        assert isinstance(req, HasSentiment)
        assert isinstance(req, HasKeyword)

    def test_mixin_fields_accessible(self):
        """Fields declared by mixins are accessible on schema instances."""
        req = RequirementResponse(
            title="测试", description="desc",
            source_platform="github", source_url="https://example.com/1",
            sentiment="moderate", emotion="neutral", confidence=0.5,
            mention_count=1, keyword="test",
        )
        assert req.source_platform == "github"
        assert req.sentiment == "moderate"
        assert req.keyword == "test"
        assert req.confidence == 0.5

    def test_mixins_are_plain_classes_not_basemodels(self):
        """Mixins are plain Python classes, not Pydantic BaseModels."""
        assert not hasattr(HasSource, "model_fields")
        assert not hasattr(HasSentiment, "model_config")


class TestEntityRegistry:
    def test_core_entities_registered(self):
        """All core entity types are in the registry."""
        expected = {"requirement", "opportunity", "proposal", "report",
                    "crawl_task", "pipeline_run", "verification", "trending_project"}
        assert expected.issubset(set(ENTITY_REGISTRY.keys()))

    def test_every_entry_is_frozen_entity_info(self):
        """Every registry entry is an EntityInfo dataclass."""
        for info in ENTITY_REGISTRY.values():
            assert isinstance(info, EntityInfo)

    def test_display_metadata_present(self):
        """Every entity has display_name, icon, and schema_ref."""
        for key, info in ENTITY_REGISTRY.items():
            assert info.type_name == key
            assert info.display_name
            assert info.icon
            assert info.schema_ref

    def test_storage_is_vault_or_database(self):
        """storage is always 'vault' or 'database'."""
        for info in ENTITY_REGISTRY.values():
            assert info.storage in ("vault", "database")

    def test_vault_entities_have_stage(self):
        """Vault-backed entities must specify vault_stage."""
        for info in ENTITY_REGISTRY.values():
            if info.storage == "vault":
                assert info.vault_stage

    def test_get_entity_by_type_name(self):
        """get_entity looks up a single entity by its type_name."""
        info = get_entity("requirement")
        assert info.type_name == "requirement"
        assert info.display_name == "需求"

    def test_get_entity_unknown_raises_keyerror(self):
        """get_entity raises KeyError for unknown type names."""
        with pytest.raises(KeyError, match="nonexistent"):
            get_entity("nonexistent")

    def test_list_entities_returns_all(self):
        """list_entities with no filters returns all registered types."""
        assert len(list_entities()) == len(ENTITY_REGISTRY)

    def test_list_entities_filter_by_storage(self):
        """Filtering by storage returns only matching entities."""
        vault = list_entities(storage="vault")
        assert all(e.storage == "vault" for e in vault)
        db = list_entities(storage="database")
        assert all(e.storage == "database" for e in db)

    def test_list_entities_filter_by_interface(self):
        """Filtering by interface returns only matching entities."""
        has_sentiment = list_entities(interface="HasSentiment")
        assert len(has_sentiment) == 1
        assert has_sentiment[0].type_name == "requirement"

    def test_list_entities_unknown_interface_returns_empty(self):
        """Unknown interface filter returns empty list cleanly."""
        assert list_entities(interface="NonExistent") == []

    def test_entity_info_is_immutable(self):
        """EntityInfo is frozen — setting attributes raises an error."""
        info = get_entity("requirement")
        with pytest.raises(Exception):
            info.display_name = "changed"  # type: ignore[misc]
