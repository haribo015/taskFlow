from enum import StrEnum

from tortoise import fields
from tortoise.models import Model


class TaskStatus(StrEnum):
    TODO = "todo"
    IN_PROGRESS = "in_progress"
    DONE = "done"


class TaskPriority(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class Task(Model):
    id = fields.IntField(primary_key=True)
    # owned by WorkspaceService / UserService: plain ids, no cross-database foreign keys
    workspace_id = fields.IntField(db_index=True)
    title = fields.CharField(max_length=200)
    description = fields.TextField(default="")
    status = fields.CharEnumField(TaskStatus, max_length=16, default=TaskStatus.TODO)
    priority = fields.CharEnumField(TaskPriority, max_length=16, default=TaskPriority.MEDIUM)
    assignee_id = fields.IntField(null=True, db_index=True)
    due_date = fields.DateField(null=True)
    created_by = fields.IntField()
    created_at = fields.DatetimeField(auto_now_add=True)
    updated_at = fields.DatetimeField(auto_now=True)
    completed_at = fields.DatetimeField(null=True)

    class Meta:
        table = "tasks"
        ordering = ["-created_at"]
