"""Entity registry API — list entity types and their metadata."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from needradar.core.entity_registry import get_entity, list_entities

router = APIRouter(prefix="/entities", tags=["entities"])


def _serialize(e) -> dict:
    return {
        "type_name": e.type_name,
        "display_name": e.display_name,
        "display_name_en": e.display_name_en,
        "icon": e.icon,
        "storage": e.storage,
        "vault_stage": e.vault_stage,
        "links_from": list(e.links_from),
        "links_to": list(e.links_to),
        "actions": list(e.actions),
        "prominent_properties": list(e.prominent_properties),
        "interfaces": list(e.interfaces),
    }


@router.get("")
async def get_entities(
    storage: str | None = Query(None, description="Filter by storage: vault | database"),
    interface: str | None = Query(None, description="Filter by interface name"),
) -> dict[str, object]:
    """List all entity types in the NeedRadar ontology with display metadata."""
    items = list_entities(storage=storage, interface=interface)
    return {"items": [_serialize(e) for e in items], "total": len(items)}


@router.get("/{type_name}")
async def get_entity_type(type_name: str) -> dict[str, object]:
    """Get metadata for a single entity type."""
    try:
        info = get_entity(type_name)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Unknown entity type: {type_name}")
    return _serialize(info)
