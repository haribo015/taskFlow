from httpx import AsyncClient

from app.events import handle_event
from app.models import Task
from tests.conftest import FakePublisher, auth


async def create_task(client: AsyncClient, user: int = 1, **overrides) -> dict:
    payload = {"workspace_id": 10, "title": "Écrire le README", **overrides}
    response = await client.post("/api/tasks", json=payload, headers=auth(user))
    assert response.status_code == 201, response.text
    return response.json()


async def test_health(client: AsyncClient) -> None:
    assert (await client.get("/health")).json()["service"] == "task-service"


async def test_create_task_defaults_and_event(
    client: AsyncClient, publisher: FakePublisher
) -> None:
    task = await create_task(client, assignee_id=2, due_date="2030-01-31", priority="high")
    assert task["status"] == "todo"
    assert task["priority"] == "high"
    assert task["created_by"] == 1
    assert task["completed_at"] is None
    routing_key, data = publisher.events[0]
    assert routing_key == "task.created"
    assert data["id"] == task["id"] and data["assignee_id"] == 2


async def test_non_member_cannot_create_or_read(client: AsyncClient) -> None:
    response = await client.post(
        "/api/tasks", json={"workspace_id": 10, "title": "x"}, headers=auth(3)
    )
    assert response.status_code == 404

    task = await create_task(client)
    assert (await client.get(f"/api/tasks/{task['id']}", headers=auth(3))).status_code == 404
    listing = await client.get("/api/tasks?workspace_id=10", headers=auth(3))
    assert listing.status_code == 404


async def test_assignee_must_be_member(client: AsyncClient) -> None:
    response = await client.post(
        "/api/tasks", json={"workspace_id": 10, "title": "x", "assignee_id": 3}, headers=auth(1)
    )
    assert response.status_code == 422


async def test_list_with_filters(client: AsyncClient) -> None:
    await create_task(client, title="a", priority="low")
    await create_task(client, title="b", status="in_progress", assignee_id=2)
    await create_task(client, title="c", status="done", assignee_id=2)

    all_tasks = await client.get("/api/tasks?workspace_id=10", headers=auth(2))
    assert len(all_tasks.json()) == 3

    in_progress = await client.get("/api/tasks?workspace_id=10&status=in_progress", headers=auth(1))
    assert [t["title"] for t in in_progress.json()] == ["b"]

    mine = await client.get("/api/tasks/mine", headers=auth(2))
    assert {t["title"] for t in mine.json()} == {"b", "c"}


async def test_status_transitions_track_completion(
    client: AsyncClient, publisher: FakePublisher
) -> None:
    task = await create_task(client)
    url = f"/api/tasks/{task['id']}"

    done = await client.patch(url, json={"status": "done"}, headers=auth(2))
    assert done.status_code == 200
    assert done.json()["completed_at"] is not None
    assert publisher.events[-1][0] == "task.updated"

    reopened = await client.patch(url, json={"status": "in_progress"}, headers=auth(1))
    assert reopened.json()["completed_at"] is None


async def test_partial_update_can_clear_fields(client: AsyncClient) -> None:
    task = await create_task(client, assignee_id=2, due_date="2030-01-31")
    url = f"/api/tasks/{task['id']}"

    response = await client.patch(url, json={"title": "Nouveau titre"}, headers=auth(1))
    assert response.json()["assignee_id"] == 2  # untouched

    cleared = await client.patch(url, json={"assignee_id": None, "due_date": None}, headers=auth(1))
    assert cleared.json()["assignee_id"] is None
    assert cleared.json()["due_date"] is None


async def test_delete_task(client: AsyncClient, publisher: FakePublisher) -> None:
    task = await create_task(client)
    url = f"/api/tasks/{task['id']}"
    assert (await client.delete(url, headers=auth(1))).status_code == 204
    assert publisher.events[-1][0] == "task.deleted"
    assert (await client.get(url, headers=auth(1))).status_code == 404


async def test_workspace_deleted_event_removes_tasks(client: AsyncClient) -> None:
    await create_task(client)
    await create_task(client)
    await handle_event("workspace.deleted", {"data": {"workspace_id": 10}})
    assert await Task.filter(workspace_id=10).count() == 0
