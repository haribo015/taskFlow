from datetime import datetime

from pydantic import BaseModel, ConfigDict


class AssigneeStats(BaseModel):
    assignee_id: int | None
    total: int
    done: int


class ActivityRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    event: str
    actor_id: int | None
    summary: str
    occurred_at: datetime


class WorkspaceStats(BaseModel):
    workspace_id: int
    total_tasks: int
    by_status: dict[str, int]
    by_priority: dict[str, int]
    completion_rate: float
    overdue_tasks: int
    completed_last_7_days: int
    by_assignee: list[AssigneeStats]
    recent_activity: list[ActivityRead]


class MyStats(BaseModel):
    total_assigned: int
    by_status: dict[str, int]
    overdue_tasks: int
    completed_last_7_days: int
    workspaces: int
