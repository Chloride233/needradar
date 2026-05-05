"""Integration tests for verification and scheduler APIs."""

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_verification_endpoints_respond(client: AsyncClient):
    """Verification API endpoints return valid responses."""
    resp = await client.get("/api/v1/verification/results")
    assert resp.status_code == 200
    assert "items" in resp.json()
    assert "total" in resp.json()

    resp = await client.get("/api/v1/verification/stats")
    assert resp.status_code == 200
    assert "total_verifications" in resp.json()

    resp = await client.get("/api/v1/verification/reports")
    assert resp.status_code == 200
    assert "items" in resp.json()


@pytest.mark.asyncio
async def test_scheduler_full_lifecycle(client: AsyncClient):
    """Test scheduler CRUD: create -> get -> update -> trigger -> delete."""
    resp = await client.get("/api/v1/scheduler")
    assert resp.status_code == 200
    initial_total = resp.json()["total"]

    # Create
    resp = await client.post("/api/v1/scheduler", json={
        "name": "daily AI monitor",
        "keyword": "AI tools",
        "platforms": ["github", "juejin"],
        "interval_minutes": 60,
    })
    assert resp.status_code == 201
    job = resp.json()
    assert job["name"] == "daily AI monitor"
    assert job["status"] == "active"
    assert job["interval_minutes"] == 60
    assert job["run_count"] == 0
    job_id = job["id"]

    # Get by ID
    resp = await client.get(f"/api/v1/scheduler/{job_id}")
    assert resp.status_code == 200
    assert resp.json()["keyword"] == "AI tools"

    # 404 for non-existent
    resp = await client.get("/api/v1/scheduler/99999")
    assert resp.status_code == 404

    # Update
    resp = await client.patch(f"/api/v1/scheduler/{job_id}", json={
        "interval_minutes": 120,
        "keyword": "LLM agent",
    })
    assert resp.status_code == 200
    assert resp.json()["interval_minutes"] == 120

    # Pause and resume
    resp = await client.patch(f"/api/v1/scheduler/{job_id}", json={"status": "paused"})
    assert resp.json()["status"] == "paused"
    resp = await client.patch(f"/api/v1/scheduler/{job_id}", json={"status": "active"})
    assert resp.json()["status"] == "active"

    # List shows +1
    resp = await client.get("/api/v1/scheduler")
    assert resp.json()["total"] == initial_total + 1

    # Trigger
    resp = await client.post(f"/api/v1/scheduler/{job_id}/trigger")
    assert resp.status_code == 200

    # Delete
    resp = await client.delete(f"/api/v1/scheduler/{job_id}")
    assert resp.status_code == 204
    resp = await client.get("/api/v1/scheduler")
    assert resp.json()["total"] == initial_total


@pytest.mark.asyncio
async def test_scheduler_validation(client: AsyncClient):
    """Test scheduler input validation."""
    # Missing required fields
    resp = await client.post("/api/v1/scheduler", json={"keyword": "test"})
    assert resp.status_code == 422

    # Interval too small
    resp = await client.post("/api/v1/scheduler", json={
        "name": "test", "keyword": "test", "interval_minutes": 1,
    })
    assert resp.status_code == 422

    # Valid minimum
    resp = await client.post("/api/v1/scheduler", json={
        "name": "test", "keyword": "test",
        "platforms": ["github"], "interval_minutes": 10,
    })
    assert resp.status_code == 201
    await client.delete(f"/api/v1/scheduler/{resp.json()['id']}")
