"""Integration tests for gates API endpoints."""
import pytest

from needradar.models.pipeline_run import PipelineRun
from needradar.models.quality_gate import GateStatus, GateType, QualityGate


@pytest.fixture
async def run_with_gate(db_session):
    """Create a pipeline run with a quality gate."""
    run = PipelineRun(
        keyword="gate-test", status="paused", task_ids_json="[]",
        stages_json="[]", is_agent_mode=True, current_phase="material_gate", gate_status="awaiting_review",
    )
    db_session.add(run)
    await db_session.commit()

    gate = QualityGate(
        pipeline_run_id=run.id, gate_type=GateType.MATERIAL.value,
        status=GateStatus.AWAITING_REVIEW.value,
        items_json='[{"title":"item1","platform":"github","source_url":"http://test","content_preview":"test content","approved":true}]',
        items_count=1,
    )
    db_session.add(gate)
    await db_session.commit()
    return run, gate


@pytest.mark.asyncio
async def test_list_gates(client, run_with_gate):
    """GET /api/v1/gates returns gates list."""
    resp = await client.get("/api/v1/gates")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] >= 1
    assert len(data["items"]) >= 1


@pytest.mark.asyncio
async def test_list_gates_by_status(client, run_with_gate):
    """GET /api/v1/gates?status=awaiting_review filters by status."""
    resp = await client.get("/api/v1/gates", params={"status": "awaiting_review"})
    assert resp.status_code == 200
    data = resp.json()
    assert all(g["status"] == "awaiting_review" for g in data["items"])


@pytest.mark.asyncio
async def test_list_gates_by_pipeline_run_id(client, run_with_gate):
    """GET /api/v1/gates?pipeline_run_id= filters by run."""
    run, gate = run_with_gate
    resp = await client.get("/api/v1/gates", params={"pipeline_run_id": run.id})
    assert resp.status_code == 200
    data = resp.json()
    assert all(g["pipeline_run_id"] == run.id for g in data["items"])


@pytest.mark.asyncio
async def test_get_gate_detail(client, run_with_gate):
    """GET /api/v1/gates/{id} returns gate detail with items."""
    _, gate = run_with_gate
    resp = await client.get(f"/api/v1/gates/{gate.id}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["id"] == gate.id
    assert "items" in data
    assert len(data["items"]) == 1


@pytest.mark.asyncio
async def test_get_gate_not_found(client):
    """GET /api/v1/gates/99999 returns 404."""
    resp = await client.get("/api/v1/gates/99999")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_approve_gate(client, run_with_gate):
    """POST /api/v1/gates/{id}/approve approves the gate."""
    _, gate = run_with_gate
    resp = await client.post(f"/api/v1/gates/{gate.id}/approve", json={"note": "Looks good"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "approved"


@pytest.mark.asyncio
async def test_reject_gate(client, run_with_gate):
    """POST /api/v1/gates/{id}/reject rejects the gate."""
    _, gate = run_with_gate
    resp = await client.post(f"/api/v1/gates/{gate.id}/reject", json={"reason": "Bad data"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "rejected"


@pytest.mark.asyncio
async def test_edit_gate(client, run_with_gate):
    """POST /api/v1/gates/{id}/edit submits edits and approves."""
    _, gate = run_with_gate
    resp = await client.post(f"/api/v1/gates/{gate.id}/edit", json={
        "edits": [{"feedback_type": "item_removed", "entity_id": "1", "before": {"x": 1}, "reason": "test"}],
        "note": "Edited",
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "approved"


@pytest.mark.asyncio
async def test_approve_gate_not_found(client):
    """POST /api/v1/gates/99999/approve returns 404."""
    resp = await client.post("/api/v1/gates/99999/approve", json={"note": ""})
    assert resp.status_code == 400  # ValueError caught


@pytest.mark.asyncio
async def test_list_gate_feedback(client, run_with_gate):
    """GET /api/v1/gates/{id}/feedback returns feedback list."""
    _, gate = run_with_gate
    resp = await client.get(f"/api/v1/gates/{gate.id}/feedback")
    assert resp.status_code == 200
    data = resp.json()
    assert "items" in data
