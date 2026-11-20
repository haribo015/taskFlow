from enum import StrEnum

from tortoise import fields
from tortoise.models import Model


class Role(StrEnum):
    OWNER = "owner"
    ADMIN = "admin"
    MEMBER = "member"


class Workspace(Model):
    id = fields.IntField(primary_key=True)
    name = fields.CharField(max_length=100)
    description = fields.TextField(default="")
    owner_id = fields.IntField(db_index=True)
    created_at = fields.DatetimeField(auto_now_add=True)
    updated_at = fields.DatetimeField(auto_now=True)

    memberships: fields.ReverseRelation["Membership"]

    class Meta:
        table = "workspaces"


class Membership(Model):
    id = fields.IntField(primary_key=True)
    workspace: fields.ForeignKeyRelation[Workspace] = fields.ForeignKeyField(
        "models.Workspace", related_name="memberships", on_delete=fields.CASCADE
    )
    # user data is owned by UserService: we only keep the id and a display snapshot
    user_id = fields.IntField(db_index=True)
    user_email = fields.CharField(max_length=255)
    user_full_name = fields.CharField(max_length=255)
    role = fields.CharEnumField(Role, max_length=16, default=Role.MEMBER)
    joined_at = fields.DatetimeField(auto_now_add=True)

    class Meta:
        table = "memberships"
        unique_together = (("workspace", "user_id"),)
