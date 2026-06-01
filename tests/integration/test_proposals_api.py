"""Integration tests for /api/v1/proposals."""

import pytest


class TestProposalsAPI:
    @pytest.mark.asyncio
    async def test_list_empty(self, client):
        r = await client.get("/api/v1/proposals")
        assert r.status_code == 200
        assert r.json()["total"] == 0

    @pytest.mark.asyncio
    async def test_list_filters(self, client):
        r = await client.get("/api/v1/proposals?keyword=AI&page_size=10")
        assert r.status_code == 200

    @pytest.mark.asyncio
    async def test_get_404(self, client):
        assert (await client.get("/api/v1/proposals/99999")).status_code == 404

    @pytest.mark.asyncio
    async def test_prompt_404(self, client):
        assert (await client.get("/api/v1/proposals/99999/prompt")).status_code == 404

    @pytest.mark.asyncio
    async def test_generate_404(self, client):
        r = await client.post("/api/v1/proposals/generate", json={"opportunity_id": 99999})
        assert r.status_code == 404
