"""Integration tests for feedback API endpoints."""
import pytest


@pytest.mark.asyncio
async def test_list_feedback_empty(client):
    """GET /api/v1/feedback returns empty list."""
    resp = await client.get("/api/v1/feedback")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 0
    assert data["items"] == []


@pytest.mark.asyncio
async def test_list_feedback_with_filters(client):
    """GET /api/v1/feedback supports filters."""
    resp = await client.get("/api/v1/feedback", params={
        "pipeline_run_id": 1,
        "feedback_type": "item_edited",
        "page": 1,
        "page_size": 10,
    })
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_feedback_stats(client):
    """GET /api/v1/feedback/stats returns aggregated stats."""
    resp = await client.get("/api/v1/feedback/stats")
    assert resp.status_code == 200
    data = resp.json()
    assert "total" in data
    assert "by_type" in data
    assert "by_entity" in data


@pytest.mark.asyncio
async def test_derived_test_cases(client):
    """GET /api/v1/feedback/derived-test-cases returns test cases."""
    resp = await client.get("/api/v1/feedback/derived-test-cases")
    assert resp.status_code == 200
    data = resp.json()
    assert "test_cases" in data
    assert "count" in data
