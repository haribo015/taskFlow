from datetime import date, datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.models import Task, TaskPriority, TaskStatus


class TaskCreate(BaseModel):
    workspace_id: int
    title: str = Field(min_length=1, max_length=200)
    description: str = Field(default="", max_length=5000)
    status: TaskStatus = TaskStatus.TODO
    priority: TaskPriority = TaskPriority.MEDIUM
    assignee_id: int | None = None
    due_date: date | None = None


class TaskUpdate(BaseModel):
    """Partial update: only fields present in the payload are applied (``null`` clears)."""

    title: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=5000)
    status: TaskStatus | None = None
    priority: TaskPriority | None = None
    assignee_id: int | None = None
    due_date: date | None = None


class TaskRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    workspace_id: int
    title: str
    description: str
    status: TaskStatus
    priority: TaskPriority
    assignee_id: int | None
    due_date: date | None
    created_by: int
    created_at: datetime
    updated_at: datetime
    completed_at: datetime | None


def task_event_data(task: Task) -> dict[str, Any]:
    """Snapshot sent with task.* events (consumed by AnalyticsService)."""
    return TaskRead.model_validate(task).model_dump(mode="json")
