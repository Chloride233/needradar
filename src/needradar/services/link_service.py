"""EntityLink service — CRUD, traversal, and migration from legacy JSON references."""

from __future__ import annotations

import json

from loguru import logger
from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from needradar.models.link import EntityLink, LinkType
from needradar.schemas.schemas import EntityLinkCreateRequest, EntityLinkQueryRequest


class EntityLinkService:
    """Query and manage the entity relationship graph."""

    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    # -- Create ----------------------------------------------------------------

    async def create(self, req: EntityLinkCreateRequest) -> EntityLink:
        link = EntityLink(
            source_type=req.source_type,
            source_id=req.source_id,
            link_type=req.link_type.value,
            target_type=req.target_type,
            target_id=req.target_id,
            metadata_json=json.dumps(req.metadata, ensure_ascii=False),
        )
        self._db.add(link)
        await self._db.flush()
        return link

    async def batch_create(self, requests: list[EntityLinkCreateRequest]) -> list[EntityLink]:
        links = []
        for req in requests:
            link = EntityLink(
                source_type=req.source_type,
                source_id=req.source_id,
                link_type=req.link_type.value,
                target_type=req.target_type,
                target_id=req.target_id,
                metadata_json=json.dumps(req.metadata, ensure_ascii=False),
            )
            self._db.add(link)
            links.append(link)
        await self._db.flush()
        return links

    # -- Read ----------------------------------------------------------------

    async def query(self, filters: EntityLinkQueryRequest) -> tuple[list[EntityLink], int]:
        conditions = []
        if filters.source_type:
            conditions.append(EntityLink.source_type == filters.source_type)
        if filters.source_id:
            conditions.append(EntityLink.source_id == filters.source_id)
        if filters.link_type:
            conditions.append(EntityLink.link_type == filters.link_type)
        if filters.target_type:
            conditions.append(EntityLink.target_type == filters.target_type)
        if filters.target_id:
            conditions.append(EntityLink.target_id == filters.target_id)

        where = and_(*conditions) if conditions else None
        base = select(EntityLink)
        if where is not None:
            base = base.where(where)

        count_stmt = select(func.count(EntityLink.id))
        if where is not None:
            count_stmt = count_stmt.where(where)
        total = (await self._db.execute(count_stmt)).scalar_one()

        offset = (filters.page - 1) * filters.page_size
        result = await self._db.execute(
            base.order_by(EntityLink.created_at.desc())
            .offset(offset)
            .limit(filters.page_size)
        )
        return list(result.scalars().all()), total

    async def get_by_source(
        self, source_type: str, source_id: str, link_type: str | None = None,
    ) -> list[EntityLink]:
        """All links originating from a given entity (its outgoing edges)."""
        conditions = [
            EntityLink.source_type == source_type,
            EntityLink.source_id == source_id,
        ]
        if link_type:
            conditions.append(EntityLink.link_type == link_type)
        result = await self._db.execute(
            select(EntityLink).where(and_(*conditions))
        )
        return list(result.scalars().all())

    async def get_by_target(
        self, target_type: str, target_id: str, link_type: str | None = None,
    ) -> list[EntityLink]:
        """All links pointing TO a given entity (its incoming edges)."""
        conditions = [
            EntityLink.target_type == target_type,
            EntityLink.target_id == target_id,
        ]
        if link_type:
            conditions.append(EntityLink.link_type == link_type)
        result = await self._db.execute(
            select(EntityLink).where(and_(*conditions))
        )
        return list(result.scalars().all())

    async def get_neighbors(
        self, entity_type: str, entity_id: str,
    ) -> dict[str, list[EntityLink]]:
        """All links where the entity appears as either source or target."""
        outgoing = await self.get_by_source(entity_type, entity_id)
        incoming = await self.get_by_target(entity_type, entity_id)
        return {"outgoing": outgoing, "incoming": incoming}

    # -- Delete ----------------------------------------------------------------

    async def get_by_id(self, link_id: int) -> EntityLink | None:
        result = await self._db.execute(
            select(EntityLink).where(EntityLink.id == link_id)
        )
        return result.scalar_one_or_none()

    async def delete(self, link_id: int) -> bool:
        link = await self.get_by_id(link_id)
        if link is None:
            return False
        await self._db.delete(link)
        await self._db.flush()
        return True

    async def delete_by_entity(self, entity_type: str, entity_id: str) -> int:
        """Delete all links where the entity appears as source or target. Returns count."""
        result = await self._db.execute(
            select(EntityLink).where(
                or_(
                    and_(EntityLink.source_type == entity_type, EntityLink.source_id == entity_id),
                    and_(EntityLink.target_type == entity_type, EntityLink.target_id == entity_id),
                )
            )
        )
        links = list(result.scalars().all())
        for link in links:
            await self._db.delete(link)
        await self._db.flush()
        return len(links)

    # -- Migration helpers ------------------------------------------------------

    async def migrate_opportunity_links(self) -> int:
        """Convert Opportunity.source_req_ids_json to EntityLink rows."""
        from needradar.models.opportunity import ProjectOpportunity

        result = await self._db.execute(select(ProjectOpportunity))
        opportunities = list(result.scalars().all())

        created = 0
        for opp in opportunities:
            try:
                req_titles = json.loads(opp.source_req_ids_json)
            except (json.JSONDecodeError, TypeError):
                req_titles = []

            if not req_titles:
                continue

            for title in req_titles:
                existing = await self._db.execute(
                    select(EntityLink).where(
                        EntityLink.source_type == "opportunity",
                        EntityLink.source_id == str(opp.id),
                        EntityLink.link_type == LinkType.CONTAINS.value,
                        EntityLink.target_type == "requirement",
                        EntityLink.target_id == title,
                    )
                )
                if existing.scalar_one_or_none():
                    continue

                self._db.add(EntityLink(
                    source_type="opportunity",
                    source_id=str(opp.id),
                    link_type=LinkType.CONTAINS.value,
                    target_type="requirement",
                    target_id=title,
                ))
                created += 1

        await self._db.flush()
        logger.info("migrated_opportunity_links", created=created, opportunities=len(opportunities))
        return created

    async def migrate_pipeline_links(self) -> int:
        """Convert PipelineRun.task_ids_json to EntityLink rows."""
        from needradar.models.pipeline_run import PipelineRun

        result = await self._db.execute(select(PipelineRun))
        runs = list(result.scalars().all())

        created = 0
        for run in runs:
            try:
                task_ids = json.loads(run.task_ids_json)
            except (json.JSONDecodeError, TypeError):
                task_ids = []

            if not task_ids:
                continue

            for tid in task_ids:
                existing = await self._db.execute(
                    select(EntityLink).where(
                        EntityLink.source_type == "crawl_task",
                        EntityLink.source_id == str(tid),
                        EntityLink.link_type == LinkType.EXECUTED_IN.value,
                        EntityLink.target_type == "pipeline_run",
                        EntityLink.target_id == str(run.id),
                    )
                )
                if existing.scalar_one_or_none():
                    continue

                self._db.add(EntityLink(
                    source_type="crawl_task",
                    source_id=str(tid),
                    link_type=LinkType.EXECUTED_IN.value,
                    target_type="pipeline_run",
                    target_id=str(run.id),
                ))
                created += 1

        await self._db.flush()
        logger.info("migrated_pipeline_links", created=created, runs=len(runs))
        return created

    async def migrate_verification_links(self) -> int:
        """Convert VerificationResult.report_title to EntityLink rows."""
        from needradar.models.verification import VerificationResult

        result = await self._db.execute(select(VerificationResult))
        verifications = list(result.scalars().all())

        created = 0
        for vf in verifications:
            if not vf.report_title or not vf.report_title.strip():
                continue

            existing = await self._db.execute(
                select(EntityLink).where(
                    EntityLink.source_type == "verification",
                    EntityLink.source_id == str(vf.id),
                    EntityLink.link_type == LinkType.VERIFIED_BY.value,
                    EntityLink.target_type == "report",
                    EntityLink.target_id == vf.report_title,
                )
            )
            if existing.scalar_one_or_none():
                continue

            self._db.add(EntityLink(
                source_type="verification",
                source_id=str(vf.id),
                link_type=LinkType.VERIFIED_BY.value,
                target_type="report",
                target_id=vf.report_title,
            ))
            created += 1

        await self._db.flush()
        logger.info("migrated_verification_links", created=created, verifications=len(verifications))
        return created

    async def migrate_all(self) -> dict[str, int]:
        """Run all migration helpers in a single transaction. Returns counts."""
        counts = {
            "opportunity_links": await self.migrate_opportunity_links(),
            "pipeline_links": await self.migrate_pipeline_links(),
            "verification_links": await self.migrate_verification_links(),
        }
        logger.info("migration_complete", **counts)
        return counts
