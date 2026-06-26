"""Integration tests for reports API endpoints."""
import pytest


@pytest.mark.asyncio
async def test_list_reports_empty(client):
    """GET /api/v1/reports returns empty list."""
    resp = await client.get("/api/v1/reports")
    assert resp.status_code == 200
    data = resp.json()
    assert "items" in data


@pytest.mark.asyncio
async def test_download_report_not_found(client):
    """GET /api/v1/reports/download/nonexistent returns 404."""
    resp = await client.get("/api/v1/reports/download/nonexistent")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_delete_report_not_found(client):
    """DELETE /api/v1/reports/nonexistent returns 404."""
    resp = await client.delete("/api/v1/reports/nonexistent")
    assert resp.status_code == 404
