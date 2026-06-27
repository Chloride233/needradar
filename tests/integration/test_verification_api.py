"""Integration tests for verification API endpoints."""
import pytest
from needradar.models.verification import VerificationResult, VerificationStatus


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


@pytest.mark.asyncio
async def test_verification_result_detail_feedback_and_report_filters(client, db_session):
    """Verification detail endpoints can fetch, update, and filter a saved result."""
    result = VerificationResult(
        report_title="test-report",
        status=VerificationStatus.COMPLETED,
        reviewer_note="initial",
    )
    db_session.add(result)
    await db_session.commit()
    await db_session.refresh(result)

    resp = await client.get(f"/api/v1/verification/results/{result.id}")
    assert resp.status_code == 200
    assert resp.json()["report_title"] == "test-report"

    resp = await client.post(
        f"/api/v1/verification/results/{result.id}/feedback",
        json={"reviewer_note": "reviewed", "verdict_override": "supported"},
    )
    assert resp.status_code == 200
    assert resp.json()["reviewer_note"] == "reviewed"
    assert resp.json()["verdict_override"] == "supported"

    resp = await client.get("/api/v1/verification/results/by-report/test-report")
    assert resp.status_code == 200
    assert resp.json()["total"] == 1
