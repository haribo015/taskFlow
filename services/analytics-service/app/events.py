"""Consumes task.* and workspace.* events to maintain the analytics projection."""

import logging
from datetime import UTC, date, datetime
from typing import Any

from app.models import ActivityEvent, TaskSnapshot

logger = logging.getLogger(__name__)

QUEUE_NAME = "analytics-service.events"
ROUTING_KEYS = ("task.*", "workspace.*")


def _parse_datetime(value: str | None) -> datetime | None:
    return datetime.fromisoformat(value) if value else None


def _parse_date(value: str | None) -> date | None:
    return date.fromisoformat(value) if value else None


def describe(routing_key: str, data: dict[str, Any]) -> str:
    title = data.get("title", "")
    return {
        "task.created": f"Tâche créée : {title}",
        "task.updated": f"Tâche mise à jour : {title} ({data.get('status', '')})",
        "task.deleted": f"Tâche supprimée : {title}",
        "workspace.created": f"Espace créé : {data.get('name', '')}",
        "workspace.updated": f"Espace renommé : {data.get('name', '')}",
        "workspace.member_added": f"Membre #{data.get('user_id')} ajouté",
        "workspace.member_removed": f"Membre #{data.get('user_id')} retiré",
    }.get(routing_key, routing_key)[:255]


async def handle_event(routing_key: str, event: dict[str, Any]) -> None:
    data: dict[str, Any] = event.get("data", {})

    if routing_key in ("task.created", "task.updated"):
        await TaskSnapshot.update_or_create(
            task_id=data["id"],
            defaults={
                "workspace_id": data["workspace_id"],
                "title": data["title"],
                "status": data["status"],
                "priority": data["priority"],
                "assignee_id": data.get("assignee_id"),
                "due_date": _parse_date(data.get("due_date")),
                "created_at": _parse_datetime(data["created_at"]),
                "completed_at": _parse_datetime(data.get("completed_at")),
            },
        )
    elif routing_key == "task.deleted":
        await TaskSnapshot.filter(task_id=data["id"]).delete()
    elif routing_key == "workspace.deleted":
        workspace_id = data["workspace_id"]
        await TaskSnapshot.filter(workspace_id=workspace_id).delete()
        await ActivityEvent.filter(workspace_id=workspace_id).delete()
        return

    await ActivityEvent.create(
        event=routing_key,
        workspace_id=data.get("workspace_id"),
        actor_id=event.get("actor_id"),
        summary=describe(routing_key, data),
        occurred_at=_parse_datetime(event.get("occurred_at")) or datetime.now(UTC),
    )
