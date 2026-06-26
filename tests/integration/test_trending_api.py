"""Integration tests for trending API endpoints."""
import pytest


@pytest.mark.asyncio
async def test_list_trending_empty(client):
    """GET /api/v1/trending returns empty list."""
    resp = await client.get("/api/v1/trending")
    assert resp.status_code == 200
    data = resp.json()
    assert "items" in data
    assert data["total"] == 0


@pytest.mark.asyncio
async def test_list_trending_with_filters(client):
    """GET /api/v1/trending supports language and since filters."""
    resp = await client.get("/api/v1/trending", params={"language": "Python", "since": "weekly"})
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_list_trending_with_pagination(client):
    """GET /api/v1/trending supports pagination."""
    resp = await client.get("/api/v1/trending", params={"page": 1, "page_size": 5})
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_get_languages(client):
    """GET /api/v1/trending/languages returns language list."""
    resp = await client.get("/api/v1/trending/languages")
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


@pytest.mark.asyncio
async def test_trending_stats(client):
    """GET /api/v1/trending/stats returns stats."""
    resp = await client.get("/api/v1/trending/stats")
    assert resp.status_code == 200
    data = resp.json()
    assert "language_distribution" in data
    assert "total_projects" in data
    assert "snapshots_available" in data


@pytest.mark.asyncio
async def test_trending_suggest_keywords(client):
    """GET /api/v1/trending/suggest-keywords returns suggestions."""
    resp = await client.get("/api/v1/trending/suggest-keywords")
    assert resp.status_code == 200
    data = resp.json()
    assert "projects" in data
