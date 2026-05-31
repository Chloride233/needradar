"""Integration tests for health, dashboard, and LLM config endpoints."""
import pytest


class TestHealth:
    @pytest.mark.asyncio
    async def test_health_check(self, client):
        resp = await client.get("/api/v1/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert data["version"] == "0.1.0"

    @pytest.mark.asyncio
    async def test_health_detail(self, client):
        resp = await client.get("/api/v1/health/detail")
        assert resp.status_code == 200
        data = resp.json()
        assert "components" in data
        assert "vault" in data["components"]


class TestLLMConfig:
    @pytest.mark.asyncio
    async def test_list_presets(self, client):
        resp = await client.get("/api/v1/llm/presets")
        assert resp.status_code == 200
        data = resp.json()
        assert "presets" in data
        presets = data["presets"]
        assert len(presets) == 2
        ids = [p["id"] for p in presets]
        assert "deepseek-v4-pro" in ids
        assert "deepseek-v4-flash" in ids

    @pytest.mark.asyncio
    async def test_presets_have_required_fields(self, client):
        resp = await client.get("/api/v1/llm/presets")
        data = resp.json()
        assert "presets" in data
        for p in data["presets"]:
            assert "health" in p
            assert "has_api_key" in p

    @pytest.mark.asyncio
    async def test_update_unknown_preset_404(self, client):
        resp = await client.put(
            "/api/v1/llm/presets/nonexistent",
            json={"api_key": "sk-test", "temperature": 0.5},
        )
        assert resp.status_code == 404


class TestScheduler:
    @pytest.mark.asyncio
    async def test_list_jobs_empty(self, client):
        resp = await client.get("/api/v1/scheduler")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 0

    @pytest.mark.asyncio
    async def test_get_job_not_found(self, client):
        resp = await client.get("/api/v1/scheduler/9999")
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_delete_job_not_found(self, client):
        resp = await client.delete("/api/v1/scheduler/9999")
        assert resp.status_code == 404
