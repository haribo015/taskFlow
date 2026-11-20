from datetime import datetime
from typing import Literal

from pydantic import BaseModel, EmailStr, Field

from app.models import Role


class WorkspaceCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    description: str = Field(default="", max_length=1000)


class WorkspaceUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    description: str | None = Field(default=None, max_length=1000)


class WorkspaceRead(BaseModel):
    id: int
    name: str
    description: str
    owner_id: int
    created_at: datetime
    my_role: Role
    member_count: int


class MemberAdd(BaseModel):
    email: EmailStr
    role: Literal[Role.ADMIN, Role.MEMBER] = Role.MEMBER


class MemberRead(BaseModel):
    user_id: int
    email: str
    full_name: str
    role: Role
    joined_at: datetime
