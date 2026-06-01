"""Unit tests for EntityLink model, EntityLinkService, and migration helpers."""

from __future__ import annotations

import json

import pytest
import pytest_asyncio
from sqlalchemy import select

from needradar.models.link import EntityLink, LinkType
from needradar.models.opportunity import ProjectOpportunity
from needradar.models.pipeline_run import PipelineRun
from needradar.models.verification import VerificationResult
from needradar.schemas.schemas import EntityLinkCreateRequest, EntityLinkQueryRequest
from needradar.services.link_service import EntityLinkService


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def link_service(db_session):
    return EntityLinkService(db_session)


# ---------------------------------------------------------------------------
# EntityLink model
# ---------------------------------------------------------------------------


class TestEntityLinkModel:
    async def test_create_minimal(self, db_session):
        """Creating an EntityLink with required fields stores to DB."""
        link = EntityLink(
            source_type="requirement",
            source_id="vault/02-需求池/test.md",
            link_type="derived_from",
            target_type="raw_discussion",
            target_id="vault/01-原始素材库/灵感剪报/source.md",
        )
        db_session.add(link)
        await db_session.commit()
        await db_session.refresh(link)

        assert link.id is not None
        assert link.source_type == "requirement"
        assert link.source_id == "vault/02-需求池/test.md"
        assert link.link_type == "derived_from"
        assert link.target_type == "raw_discussion"
        assert link.target_id == "vault/01-原始素材库/灵感剪报/source.md"
        assert link.metadata_json == "{}"
        assert link.created_at is not None

    async def test_metadata_stored_and_retrieved(self, db_session):
        """metadata_json round-trips a JSON dict correctly."""
        link = EntityLink(
            source_type="report",
            source_id="report-1",
            link_type="references",
            target_type="requirement",
            target_id="req-1",
            metadata_json=json.dumps({"confidence": 0.92, "context": "explicit mention"}),
        )
        db_session.add(link)
        await db_session.commit()
        await db_session.refresh(link)

        meta = json.loads(link.metadata_json)
        assert meta["confidence"] == 0.92
        assert meta["context"] == "explicit mention"

    def test_link_type_enum_values(self):
        """LinkType enum covers all documented relationship types."""
        assert LinkType.DERIVED_FROM == "derived_from"
        assert LinkType.CONTAINS == "contains"
        assert LinkType.GENERATES == "generates"
        assert LinkType.REFERENCES == "references"
        assert LinkType.VERIFIED_BY == "verified_by"
        assert LinkType.EXECUTED_IN == "executed_in"

    async def test_timestamp_mixin_inherited(self, db_session):
        """EntityLink inherits created_at/updated_at from TimestampMixin."""
        link = EntityLink(
            source_type="a", source_id="1", link_type="references",
            target_type="b", target_id="2",
        )
        db_session.add(link)
        await db_session.commit()
        await db_session.refresh(link)

        assert link.created_at is not None
        assert link.updated_at is not None


# ---------------------------------------------------------------------------
# EntityLinkService — CRUD
# ---------------------------------------------------------------------------


class TestEntityLinkServiceCRUD:
    async def test_create_and_query(self, link_service):
        """create() persists a link; query() retrieves it by filters."""
        req = EntityLinkCreateRequest(
            source_type="opportunity", source_id="42",
            link_type="contains", target_type="requirement",
            target_id="离线编辑支持",
        )
        link = await link_service.create(req)
        assert link.id is not None

        results, total = await link_service.query(
            EntityLinkQueryRequest(source_type="opportunity")
        )
        assert total == 1
        assert results[0].source_id == "42"
        assert results[0].link_type == "contains"

    async def test_batch_create(self, link_service):
        """batch_create creates multiple links in one call."""
        requests = [
            EntityLinkCreateRequest(
                source_type="opportunity", source_id="1",
                link_type="contains", target_type="requirement", target_id=f"req-{i}",
            )
            for i in range(5)
        ]
        links = await link_service.batch_create(requests)
        assert len(links) == 5
        for link in links:
            assert link.id is not None

        _, total = await link_service.query(EntityLinkQueryRequest())
        assert total == 5

    async def test_get_by_source_filters_by_link_type(self, link_service):
        """get_by_source returns only links matching the optional link_type."""
        await link_service.create(EntityLinkCreateRequest(
            source_type="report", source_id="r1", link_type="references",
            target_type="requirement", target_id="req-a",
        ))
        await link_service.create(EntityLinkCreateRequest(
            source_type="report", source_id="r1", link_type="references",
            target_type="requirement", target_id="req-b",
        ))
        await link_service.create(EntityLinkCreateRequest(
            source_type="report", source_id="r1", link_type="derived_from",
            target_type="raw_discussion", target_id="raw-1",
        ))

        refs = await link_service.get_by_source("report", "r1", link_type="references")
        assert len(refs) == 2

        all_links = await link_service.get_by_source("report", "r1")
        assert len(all_links) == 3

    async def test_get_by_target_returns_incoming_edges(self, link_service):
        """get_by_target finds all links pointing TO an entity."""
        for i in range(3):
            await link_service.create(EntityLinkCreateRequest(
                source_type="report", source_id=f"report-{i}",
                link_type="references", target_type="requirement", target_id="shared-req",
            ))

        incoming = await link_service.get_by_target("requirement", "shared-req")
        assert len(incoming) == 3
        assert all(link.link_type == "references" for link in incoming)

    async def test_get_neighbors_returns_both_directions(self, link_service):
        """get_neighbors returns outgoing and incoming edges."""
        await link_service.create(EntityLinkCreateRequest(
            source_type="opportunity", source_id="opp-1",
            link_type="contains", target_type="requirement", target_id="req-1",
        ))
        await link_service.create(EntityLinkCreateRequest(
            source_type="proposal", source_id="prop-1",
            link_type="generates", target_type="opportunity", target_id="opp-1",
        ))

        neighbors = await link_service.get_neighbors("opportunity", "opp-1")
        assert len(neighbors["outgoing"]) == 1  # opp-1 -> req-1
        assert len(neighbors["incoming"]) == 1   # prop-1 -> opp-1
        assert neighbors["outgoing"][0].link_type == "contains"
        assert neighbors["incoming"][0].link_type == "generates"

    async def test_delete_removes_link(self, link_service):
        """delete() removes a link by ID, returns True. Deleting again returns False."""
        link = await link_service.create(EntityLinkCreateRequest(
            source_type="a", source_id="1", link_type="references",
            target_type="b", target_id="2",
        ))
        assert await link_service.delete(link.id) is True
        assert await link_service.delete(link.id) is False

        _, total = await link_service.query(EntityLinkQueryRequest())
        assert total == 0

    async def test_delete_by_entity_removes_all_references(self, link_service):
        """delete_by_entity removes links where the entity is source OR target."""
        await link_service.create(EntityLinkCreateRequest(
            source_type="opportunity", source_id="opp-del",
            link_type="contains", target_type="requirement", target_id="req-1",
        ))
        await link_service.create(EntityLinkCreateRequest(
            source_type="proposal", source_id="prop-1",
            link_type="generates", target_type="opportunity", target_id="opp-del",
        ))

        count = await link_service.delete_by_entity("opportunity", "opp-del")
        assert count == 2

        _, total = await link_service.query(EntityLinkQueryRequest())
        assert total == 0

    async def test_query_pagination(self, link_service):
        """query respects page and page_size for largish result sets."""
        for i in range(25):
            await link_service.create(EntityLinkCreateRequest(
                source_type="test", source_id=str(i), link_type="references",
                target_type="target", target_id=f"t-{i}",
            ))

        results, total = await link_service.query(
            EntityLinkQueryRequest(source_type="test", page=1, page_size=10)
        )
        assert len(results) == 10
        assert total == 25

        results2, _ = await link_service.query(
            EntityLinkQueryRequest(source_type="test", page=3, page_size=10)
        )
        assert len(results2) == 5

    async def test_query_no_filters_returns_all(self, link_service):
        """query with no filters returns all links in the table."""
        for i in range(3):
            await link_service.create(EntityLinkCreateRequest(
                source_type="a", source_id=str(i), link_type="references",
                target_type="b", target_id=str(i),
            ))

        results, total = await link_service.query(EntityLinkQueryRequest())
        assert total == 3

    async def test_query_empty_result(self, link_service):
        """query returns empty list and zero total when nothing matches."""
        results, total = await link_service.query(
            EntityLinkQueryRequest(source_type="nonexistent")
        )
        assert results == []
        assert total == 0


# ---------------------------------------------------------------------------
# Migration helpers
# ---------------------------------------------------------------------------


class TestMigrationHelpers:
    async def test_migrate_opportunity_links(self, db_session, link_service):
        """migrate_opportunity_links converts source_req_ids_json to EntityLink rows."""
        opp = ProjectOpportunity(
            keyword="test-kw",
            title="Test Opportunity",
            source_req_ids_json=json.dumps(["需求A", "需求B", "需求C"]),
        )
        db_session.add(opp)
        await db_session.commit()
        await db_session.refresh(opp)

        created = await link_service.migrate_opportunity_links()
        assert created == 3

        links, _ = await link_service.query(
            EntityLinkQueryRequest(source_type="opportunity", source_id=str(opp.id))
        )
        assert len(links) == 3
        target_titles = {link.target_id for link in links}
        assert target_titles == {"需求A", "需求B", "需求C"}
        for link in links:
            assert link.link_type == LinkType.CONTAINS.value

    async def test_migrate_opportunity_links_idempotent(self, db_session, link_service):
        """Running migration twice on the same data creates no duplicates."""
        opp = ProjectOpportunity(
            keyword="test-kw",
            title="Dedup Test",
            source_req_ids_json=json.dumps(["需求X"]),
        )
        db_session.add(opp)
        await db_session.commit()

        first = await link_service.migrate_opportunity_links()
        second = await link_service.migrate_opportunity_links()

        assert first == 1
        assert second == 0

    async def test_migrate_opportunity_empty_json(self, db_session, link_service):
        """Empty source_req_ids_json produces zero links."""
        opp = ProjectOpportunity(
            keyword="test-kw",
            title="Empty",
            source_req_ids_json="[]",
        )
        db_session.add(opp)
        await db_session.commit()

        created = await link_service.migrate_opportunity_links()
        assert created == 0

    async def test_migrate_pipeline_links(self, db_session, link_service):
        """migrate_pipeline_links converts task_ids_json to EntityLink rows."""
        run = PipelineRun(
            keyword="test-kw",
            task_ids_json=json.dumps([10, 20, 30]),
        )
        db_session.add(run)
        await db_session.commit()
        await db_session.refresh(run)

        created = await link_service.migrate_pipeline_links()
        assert created == 3

        links, _ = await link_service.query(
            EntityLinkQueryRequest(target_type="pipeline_run", target_id=str(run.id))
        )
        assert len(links) == 3
        source_ids = {link.source_id for link in links}
        assert source_ids == {"10", "20", "30"}
        for link in links:
            assert link.link_type == LinkType.EXECUTED_IN.value

    async def test_migrate_pipeline_links_idempotent(self, db_session, link_service):
        """Pipeline migration is idempotent across re-runs."""
        run = PipelineRun(
            keyword="test-kw",
            task_ids_json=json.dumps([99]),
        )
        db_session.add(run)
        await db_session.commit()

        first = await link_service.migrate_pipeline_links()
        second = await link_service.migrate_pipeline_links()
        assert first == 1
        assert second == 0

    async def test_migrate_verification_links(self, db_session, link_service):
        """migrate_verification_links converts report_title to EntityLink rows."""
        vf = VerificationResult(
            report_title="My Analysis Report",
        )
        db_session.add(vf)
        await db_session.commit()
        await db_session.refresh(vf)

        created = await link_service.migrate_verification_links()
        assert created == 1

        links, _ = await link_service.query(
            EntityLinkQueryRequest(source_type="verification", source_id=str(vf.id))
        )
        assert len(links) == 1
        assert links[0].link_type == LinkType.VERIFIED_BY.value
        assert links[0].target_id == "My Analysis Report"

    async def test_migrate_verification_empty_title_skipped(self, db_session, link_service):
        """Verification with empty report_title is skipped by the migration."""
        vf = VerificationResult(report_title="")
        db_session.add(vf)
        await db_session.commit()

        created = await link_service.migrate_verification_links()
        assert created == 0

    async def test_migrate_all_runs_all_three(self, db_session, link_service):
        """migrate_all runs all three migrations and returns combined counts."""
        opp = ProjectOpportunity(
            keyword="all-test",
            title="All Test Opp",
            source_req_ids_json=json.dumps(["R1", "R2"]),
        )
        run = PipelineRun(
            keyword="all-test",
            task_ids_json=json.dumps([1]),
        )
        vf = VerificationResult(report_title="All Test Report")
        db_session.add_all([opp, run, vf])
        await db_session.commit()

        counts = await link_service.migrate_all()
        assert counts["opportunity_links"] == 2
        assert counts["pipeline_links"] == 1
        assert counts["verification_links"] == 1
        assert sum(counts.values()) == 4

        _, total = await link_service.query(EntityLinkQueryRequest())
        assert total == 4
