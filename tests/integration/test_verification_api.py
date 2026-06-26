"""Integration tests for verification API endpoints."""
import pytest


@pytest.mark.asyncio
async def test_list_verification_results(client):
    """GET /api/v1/verification/results returns list."""
    resp = await client.get("/api/v1/verification/results")
    assert resp.status_code == 200
    data = resp.json()
    assert "items" in data
    assert "total" in data


@pytest.mark.asyncio
async def test_list_verification_results_with_pagination(client):
    """GET /api/v1/verification/results supports pagination."""
    resp = await client.get("/api/v1/verification/results", params={"page": 1, "page_size": 5})
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_verify_not_found(client):
    """POST /api/v1/verification/verify/nonexistent returns error."""
    resp = await client.post("/api/v1/verification/verify/nonexistent")
    assert resp.status_code in (404, 500)
