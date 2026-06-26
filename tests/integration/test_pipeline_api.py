"""Integration tests for /api/v1/pipeline."""

import pytest

from needradar.models.pipeline_run import PipelineRun


class TestPipelineAPI:
    @pytest.mark.asyncio
    async def test_list_empty(self, client):
        r = await client.get("/api/v1/pipeline/runs")
        assert r.status_code == 200
        assert r.json()["total"] == 0

    @pytest.mark.asyncio
    async def test_list_status(self, client):
        r = await client.get("/api/v1/pipeline/runs?status=completed")
        assert r.status_code == 200

    @pytest.mark.asyncio
    async def test_list_comma_status(self, client):
        """Comma-separated status filter."""
        r = await client.get("/api/v1/pipeline/runs?status=running,paused")
        assert r.status_code == 200

    @pytest.mark.asyncio
    async def test_list_with_runs(self, client, db_session):
        """List returns runs when they exist."""
        run = PipelineRun(
            keyword="test", status="completed", task_ids_json="[]",
            stages_json="[]", is_agent_mode=False,
        )
        db_session.add(run)
        await db_session.commit()

        r = await client.get("/api/v1/pipeline/runs")
        assert r.status_code == 200
        assert r.json()["total"] >= 1

    @pytest.mark.asyncio
    async def test_get_run(self, client, db_session):
        """GET /api/v1/pipeline/runs/{id} returns run detail."""
        run = PipelineRun(
            keyword="detail-test", status="running", task_ids_json="[1,2]",
            stages_json='["crawl"]', is_agent_mode=True,
            current_phase="crawling", gate_status="none",
        )
        db_session.add(run)
        await db_session.commit()

        r = await client.get(f"/api/v1/pipeline/runs/{run.id}")
        assert r.status_code == 200
        data = r.json()
        assert data["keyword"] == "detail-test"
        assert data["is_agent_mode"] is True
        assert data["current_phase"] == "crawling"

    @pytest.mark.asyncio
    async def test_get_404(self, client):
        assert (await client.get("/api/v1/pipeline/runs/99999")).status_code == 404

    @pytest.mark.asyncio
    async def test_resume_404(self, client):
        assert (await client.post("/api/v1/pipeline/runs/99999/resume")).status_code == 404
