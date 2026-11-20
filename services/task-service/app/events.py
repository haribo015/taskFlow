"""Events consumed by TaskService."""

import logging
from typing import Any

from app.models import Task

logger = logging.getLogger(__name__)

QUEUE_NAME = "task-service.workspace-events"
ROUTING_KEYS = ("workspace.deleted",)


async def handle_event(routing_key: str, event: dict[str, Any]) -> None:
    if routing_key == "workspace.deleted":
        workspace_id = event["data"]["workspace_id"]
        deleted = await Task.filter(workspace_id=workspace_id).delete()
        logger.info("Workspace %s deleted: removed %s task(s)", workspace_id, deleted)
