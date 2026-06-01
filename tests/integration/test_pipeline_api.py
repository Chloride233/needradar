"""Integration tests for /api/v1/pipeline."""

import pytest


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
    async def test_get_404(self, client):
        assert (await client.get("/api/v1/pipeline/runs/99999")).status_code == 404

    @pytest.mark.asyncio
    async def test_resume_404(self, client):
        assert (await client.post("/api/v1/pipeline/runs/99999/resume")).status_code == 404
