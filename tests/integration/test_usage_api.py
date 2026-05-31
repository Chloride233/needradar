"""Integration tests for usage API endpoints."""
import pytest


@pytest.mark.asyncio
async def test_usage_summary_empty(client):
    resp = await client.get("/api/v1/usage/summary")
    assert resp.status_code == 200
    data = resp.json()
    assert data["requests"] == 0
    assert data["total_cost_cny"] == 0.0


@pytest.mark.asyncio
async def test_usage_summary_with_days(client):
    resp = await client.get("/api/v1/usage/summary?days=7")
    assert resp.status_code == 200
    assert resp.json()["days"] == 7


@pytest.mark.asyncio
async def test_usage_trend_empty(client):
    resp = await client.get("/api/v1/usage/trend")
    assert resp.status_code == 200
    assert resp.json() == []


@pytest.mark.asyncio
async def test_usage_model_stats_empty(client):
    resp = await client.get("/api/v1/usage/model-stats")
    assert resp.status_code == 200
    assert resp.json() == []


@pytest.mark.asyncio
async def test_usage_records_empty(client):
    resp = await client.get("/api/v1/usage/records")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 0


@pytest.mark.asyncio
async def test_usage_records_with_filters(client):
    resp = await client.get("/api/v1/usage/records?model=v4&call_type=extraction")
    assert resp.status_code == 200
    assert resp.json()["total"] == 0


@pytest.mark.asyncio
async def test_usage_budget(client):
    resp = await client.get("/api/v1/usage/budget")
    assert resp.status_code == 200
    data = resp.json()
    assert "alerts" in data
    assert "daily_limit" in data


@pytest.mark.asyncio
async def test_usage_records_pagination(client):
    resp = await client.get("/api/v1/usage/records?limit=10&offset=0")
    assert resp.status_code == 200
    assert resp.json()["total"] == 0
