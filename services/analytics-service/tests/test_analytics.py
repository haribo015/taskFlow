from datetime import UTC, date, datetime, timedelta

from httpx import AsyncClient

from app.events import handle_event
from app.models import ActivityEvent, TaskSnapshot
from tests.conftest import auth

NOW = datetime.now(UTC)


def task_event(task_id: int, *, workspace_id: int = 10, **fields) -> dict:
    data = {
        "id": task_id,
        "workspace_id": workspace_id,
        "title": f"Tâche {task_id}",
        "status": "todo",
        "priority": "medium",
        "assignee_id": None,
        "due_date": None,
        "created_at": NOW.isoformat(),
        "completed_at": None,
        **fields,
    }
    return {"event": "task", "occurred_at": NOW.isoformat(), "actor_id": 1, "data": data}


async def seed() -> None:
    yesterday = (date.today() - timedelta(days=1)).isoformat()
    await handle_event("task.created", task_event(1, assignee_id=1, priority="high"))
    await handle_event("task.created", task_event(2, assignee_id=2, due_date=yesterday))
    await handle_event("task.created", task_event(3, assignee_id=1))
    await handle_event(
        "task.updated",
        task_event(3, assignee_id=1, status="done", completed_at=NOW.isoformat()),
    )
    await handle_event("task.created", task_event(4, workspace_id=20, assignee_id=1))


async def test_health(client: AsyncClient) -> None:
    assert (await client.get("/health")).json()["service"] == "analytics-service"


async def test_events_build_projection() -> None:
    await seed()
    assert await TaskSnapshot.all().count() == 4
    assert (await TaskSnapshot.get(task_id=3)).status == "done"

    await handle_event("task.deleted", task_event(4, workspace_id=20))
    assert not await TaskSnapshot.exists(task_id=4)
    assert await ActivityEvent.filter(event="task.deleted").count() == 1


async def test_workspace_stats(client: AsyncClient) -> None:
    await seed()
    response = await client.get("/api/analytics/workspaces/10", headers=auth(1))
    assert response.status_code == 200
    body = response.json()
    assert body["total_tasks"] == 3
    assert body["by_status"] == {"todo": 2, "in_progress": 0, "done": 1}
    assert body["by_priority"] == {"low": 0, "medium": 2, "high": 1}
    assert body["completion_rate"] == 0.333
    assert body["overdue_tasks"] == 1
    assert body["completed_last_7_days"] == 1
    assert body["by_assignee"][0] == {"assignee_id": 1, "total": 2, "done": 1}
    assert len(body["recent_activity"]) == 4


async def test_workspace_stats_forbidden_for_non_member(client: AsyncClient) -> None:
    response = await client.get("/api/analytics/workspaces/10", headers=auth(3))
    assert response.status_code == 404


async def test_my_stats(client: AsyncClient) -> None:
    await seed()
    body = (await client.get("/api/analytics/me", headers=auth(1))).json()
    assert body == {
        "total_assigned": 3,
        "by_status": {"todo": 2, "in_progress": 0, "done": 1},
        "overdue_tasks": 0,
        "completed_last_7_days": 1,
        "workspaces": 2,
    }


async def test_workspace_deleted_purges_projection() -> None:
    await seed()
    await handle_event("workspace.deleted", {"data": {"workspace_id": 10}, "actor_id": 1})
    assert await TaskSnapshot.filter(workspace_id=10).count() == 0
    assert await ActivityEvent.filter(workspace_id=10).count() == 0
    assert await TaskSnapshot.filter(workspace_id=20).count() == 1
