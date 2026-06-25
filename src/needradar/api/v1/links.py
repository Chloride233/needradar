"""Entity link query API — traverse the entity relationship graph."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from needradar.core.database import get_db
from needradar.schemas.schemas import EntityLinkListResponse, EntityLinkResponse
from needradar.services.link_service import EntityLinkService

router = APIRouter(prefix="/links", tags=["links"])


@router.get("", response_model=EntityLinkListResponse)
async def query_links(
    entity_type: str = Query(..., min_length=1, description="Entity type: requirement, opportunity, proposal, report, crawl_task, pipeline_run, verification"),
    entity_id: str = Query(..., min_length=1, description="Entity identifier (vault path or DB primary key)"),
    direction: str = Query("both", pattern="^(outgoing|incoming|both)$"),
    link_type: str | None = Query(None),
    db: AsyncSession = Depends(get_db),
):
    """Get links for an entity. ``direction`` controls outgoing / incoming / both."""
    svc = EntityLinkService(db)

    if direction == "outgoing":
        items = await svc.get_by_source(entity_type, entity_id, link_type)
    elif direction == "incoming":
        items = await svc.get_by_target(entity_type, entity_id, link_type)
    else:
        result = await svc.get_neighbors(entity_type, entity_id)
        items = result["outgoing"] + result["incoming"]

    responses = [EntityLinkResponse.model_validate(item) for item in items]
    return EntityLinkListResponse(items=responses, total=len(responses))
