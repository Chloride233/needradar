"""Integration tests for requirements API endpoints."""
import pytest


@pytest.mark.asyncio
async def test_list_requirements_empty(client):
    """GET /api/v1/requirements returns empty list."""
    resp = await client.get("/api/v1/requirements")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 0
    assert data["items"] == []


@pytest.mark.asyncio
async def test_list_requirements_with_pagination(client):
    """GET /api/v1/requirements supports pagination."""
    resp = await client.get("/api/v1/requirements", params={"page": 1, "page_size": 10})
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_get_requirement_not_found(client):
    """GET /api/v1/requirements/nonexistent returns 404 or empty."""
    resp = await client.get("/api/v1/requirements/nonexistent")
    assert resp.status_code in (404, 200)


@pytest.mark.asyncio
async def test_requirements_summary(client):
    """GET /api/v1/requirements/summary returns summary."""
    resp = await client.get("/api/v1/requirements/summary")
    assert resp.status_code == 200
