"""Integration tests for /api/v1/opportunities."""

import pytest


class TestOpportunitiesAPI:
    @pytest.mark.asyncio
    async def test_list_empty(self, client):
        r = await client.get("/api/v1/opportunities")
        assert r.status_code == 200
        assert r.json()["total"] == 0

    @pytest.mark.asyncio
    async def test_list_filters(self, client):
        for kw in ["", "AI"]:
            r = await client.get(f"/api/v1/opportunities?keyword={kw}&min_score=50&page_size=10")
            assert r.status_code == 200

    @pytest.mark.asyncio
    async def test_get_404(self, client):
        assert (await client.get("/api/v1/opportunities/99999")).status_code == 404

    @pytest.mark.asyncio
    async def test_score_validates(self, client):
        assert (await client.post("/api/v1/opportunities/score", json={})).status_code == 422
