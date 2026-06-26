"""Integration tests for tasks API endpoints."""
import pytest


@pytest.mark.asyncio
async def test_create_task(client):
    """POST /api/v1/tasks creates a crawl task."""
    resp = await client.post("/api/v1/tasks", json={
        "keyword": "test",
        "platforms": ["github"],
    })
    assert resp.status_code == 201
    data = resp.json()
    assert data["total"] >= 1
    assert data["items"][0]["keyword"] == "test"


@pytest.mark.asyncio
async def test_create_task_no_platforms(client):
    """POST /api/v1/tasks with no platforms returns 400."""
    resp = await client.post("/api/v1/tasks", json={
        "keyword": "test",
        "platforms": [],
    })
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_list_tasks(client):
    """GET /api/v1/tasks returns task list."""
    # Create a task first
    await client.post("/api/v1/tasks", json={"keyword": "list-test", "platforms": ["github"]})

    resp = await client.get("/api/v1/tasks")
    assert resp.status_code == 200
    data = resp.json()
    assert "items" in data
    assert "total" in data


@pytest.mark.asyncio
async def test_list_tasks_with_keyword_filter(client):
    """GET /api/v1/tasks?keyword= filters by keyword."""
    await client.post("/api/v1/tasks", json={"keyword": "filter-test", "platforms": ["github"]})

    resp = await client.get("/api/v1/tasks", params={"keyword": "filter-test"})
    assert resp.status_code == 200
    data = resp.json()
    assert all(t["keyword"] == "filter-test" for t in data["items"])


@pytest.mark.asyncio
async def test_get_task(client):
    """GET /api/v1/tasks/{id} returns a single task."""
    create_resp = await client.post("/api/v1/tasks", json={"keyword": "get-test", "platforms": ["github"]})
    task_id = create_resp.json()["items"][0]["id"]

    resp = await client.get(f"/api/v1/tasks/{task_id}")
    assert resp.status_code == 200
    assert resp.json()["id"] == task_id


@pytest.mark.asyncio
async def test_get_task_not_found(client):
    """GET /api/v1/tasks/99999 returns 404."""
    resp = await client.get("/api/v1/tasks/99999")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_list_platforms(client):
    """GET /api/v1/tasks/platforms returns available platforms."""
    resp = await client.get("/api/v1/tasks/platforms")
    assert resp.status_code == 200
    data = resp.json()
    assert "platforms" in data
    assert len(data["platforms"]) > 0


@pytest.mark.asyncio
async def test_create_task_agent_mode(client):
    """POST /api/v1/tasks?mode=agent creates agent-mode pipeline."""
    resp = await client.post("/api/v1/tasks?mode=agent", json={
        "keyword": "agent-test",
        "platforms": ["github"],
    })
    assert resp.status_code == 201


@pytest.mark.asyncio
async def test_list_tasks_with_status_filter(client):
    """GET /api/v1/tasks?status=pending filters by status."""
    await client.post("/api/v1/tasks", json={"keyword": "status-test", "platforms": ["github"]})
    resp = await client.get("/api/v1/tasks", params={"status": "pending"})
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_list_tasks_with_pagination(client):
    """GET /api/v1/tasks supports pagination."""
    resp = await client.get("/api/v1/tasks", params={"page": 1, "page_size": 5})
    assert resp.status_code == 200
