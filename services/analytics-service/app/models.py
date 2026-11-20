"""Read model built from events (CQRS-style projection)."""

from tortoise import fields
from tortoise.models import Model


class TaskSnapshot(Model):
    """Latest known state of a task, as published by TaskService."""

    task_id = fields.IntField(primary_key=True, generated=False)
    workspace_id = fields.IntField(db_index=True)
    title = fields.CharField(max_length=200)
    status = fields.CharField(max_length=16)
    priority = fields.CharField(max_length=16)
    assignee_id = fields.IntField(null=True, db_index=True)
    due_date = fields.DateField(null=True)
    created_at = fields.DatetimeField()
    completed_at = fields.DatetimeField(null=True)

    class Meta:
        table = "task_snapshots"


class ActivityEvent(Model):
    id = fields.IntField(primary_key=True)
    event = fields.CharField(max_length=64)
    workspace_id = fields.IntField(null=True, db_index=True)
    actor_id = fields.IntField(null=True)
    summary = fields.CharField(max_length=255)
    occurred_at = fields.DatetimeField()

    class Meta:
        table = "activity_events"
        ordering = ["-occurred_at", "-id"]
