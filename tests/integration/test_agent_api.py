"""Integration tests for agent status API."""
import pytest


@pytest.mark.asyncio
async def test_agent_status_empty(client):
    """GET /api/v1/agent/status returns empty state."""
    resp = await client.get("/api/v1/agent/status")
    assert resp.status_code == 200
    data = resp.json()
    assert data["active_runs"] == []
    assert data["pending_gates"] == []
    assert data["recent_completed"] == []
    assert data["stats"]["total_runs"] == 0
    assert data["stats"]["total_gates"] == 0
    assert data["stats"]["approved_gates"] == 0
    assert data["stats"]["rejected_gates"] == 0
    assert data["stats"]["pending_gates_count"] == 0
