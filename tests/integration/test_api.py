import pytest


@pytest.mark.asyncio
async def test_list_tasks_empty(client):
    resp = await client.get("/api/v1/tasks")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 0
    assert data["items"] == []


@pytest.mark.asyncio
async def test_list_requirements_empty(client):
    resp = await client.get("/api/v1/requirements")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 0
    assert data["items"] == []


@pytest.mark.asyncio
async def test_dashboard_empty(client):
    resp = await client.get("/api/v1/dashboard")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total_requirements"] == 0
    assert data["total_tasks"] == 0


@pytest.mark.asyncio
async def test_get_task_not_found(client):
    resp = await client.get("/api/v1/tasks/9999")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_download_report_not_found(client):
    resp = await client.get("/api/v1/reports/download/nonexistent")
    assert resp.status_code == 404
