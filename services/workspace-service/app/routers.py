from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Response, status
from tortoise.transactions import in_transaction

from app.clients import UserDirectory, get_user_directory
from app.messaging import EventPublisher, get_publisher
from app.models import Membership, Role, Workspace
from app.schemas import MemberAdd, MemberRead, WorkspaceCreate, WorkspaceRead, WorkspaceUpdate
from app.security import AuthenticatedUser

router = APIRouter(prefix="/api/workspaces", tags=["workspaces"])

Publisher = Annotated[EventPublisher, Depends(get_publisher)]
Directory = Annotated[UserDirectory, Depends(get_user_directory)]

MANAGERS = (Role.OWNER, Role.ADMIN)


async def get_membership(workspace_id: int, user_id: int) -> Membership:
    """Return the caller's membership. Non-members get a 404 so they can't probe ids."""
    membership = await Membership.get_or_none(
        workspace_id=workspace_id, user_id=user_id
    ).prefetch_related("workspace")
    if membership is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Workspace not found")
    return membership


def require_role(membership: Membership, *roles: Role) -> None:
    if membership.role not in roles:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Insufficient workspace role")


async def to_workspace_read(workspace: Workspace, role: Role) -> WorkspaceRead:
    return WorkspaceRead(
        id=workspace.id,
        name=workspace.name,
        description=workspace.description,
        owner_id=workspace.owner_id,
        created_at=workspace.created_at,
        my_role=role,
        member_count=await Membership.filter(workspace_id=workspace.id).count(),
    )


def to_member_read(membership: Membership) -> MemberRead:
    return MemberRead(
        user_id=membership.user_id,
        email=membership.user_email,
        full_name=membership.user_full_name,
        role=membership.role,
        joined_at=membership.joined_at,
    )


@router.post("", response_model=WorkspaceRead, status_code=status.HTTP_201_CREATED)
async def create_workspace(
    payload: WorkspaceCreate, current: AuthenticatedUser, publisher: Publisher
) -> WorkspaceRead:
    async with in_transaction():
        workspace = await Workspace.create(
            name=payload.name.strip(), description=payload.description, owner_id=current.id
        )
        await Membership.create(
            workspace=workspace,
            user_id=current.id,
            user_email=current.email,
            user_full_name=current.full_name,
            role=Role.OWNER,
        )
    await publisher.publish(
        "workspace.created",
        {"workspace_id": workspace.id, "name": workspace.name, "owner_id": current.id},
        actor_id=current.id,
    )
    return await to_workspace_read(workspace, Role.OWNER)


@router.get("", response_model=list[WorkspaceRead])
async def list_my_workspaces(current: AuthenticatedUser) -> list[WorkspaceRead]:
    memberships = (
        await Membership.filter(user_id=current.id)
        .prefetch_related("workspace")
        .order_by("-joined_at")
    )
    return [await to_workspace_read(m.workspace, m.role) for m in memberships]


@router.get("/{workspace_id}", response_model=WorkspaceRead)
async def read_workspace(workspace_id: int, current: AuthenticatedUser) -> WorkspaceRead:
    membership = await get_membership(workspace_id, current.id)
    return await to_workspace_read(membership.workspace, membership.role)


@router.patch("/{workspace_id}", response_model=WorkspaceRead)
async def update_workspace(
    workspace_id: int, payload: WorkspaceUpdate, current: AuthenticatedUser, publisher: Publisher
) -> WorkspaceRead:
    membership = await get_membership(workspace_id, current.id)
    require_role(membership, *MANAGERS)
    workspace = membership.workspace
    if payload.name is not None:
        workspace.name = payload.name.strip()
    if payload.description is not None:
        workspace.description = payload.description
    await workspace.save()
    await publisher.publish(
        "workspace.updated",
        {"workspace_id": workspace.id, "name": workspace.name},
        actor_id=current.id,
    )
    return await to_workspace_read(workspace, membership.role)


@router.delete("/{workspace_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_workspace(
    workspace_id: int, current: AuthenticatedUser, publisher: Publisher
) -> Response:
    membership = await get_membership(workspace_id, current.id)
    require_role(membership, Role.OWNER)
    await membership.workspace.delete()
    # TaskService and AnalyticsService react to this event to clean up their own data
    await publisher.publish(
        "workspace.deleted", {"workspace_id": workspace_id}, actor_id=current.id
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/{workspace_id}/members", response_model=list[MemberRead])
async def list_members(workspace_id: int, current: AuthenticatedUser) -> list[MemberRead]:
    await get_membership(workspace_id, current.id)
    members = await Membership.filter(workspace_id=workspace_id).order_by("joined_at")
    return [to_member_read(m) for m in members]


@router.post(
    "/{workspace_id}/members", response_model=MemberRead, status_code=status.HTTP_201_CREATED
)
async def add_member(
    workspace_id: int,
    payload: MemberAdd,
    current: AuthenticatedUser,
    directory: Directory,
    publisher: Publisher,
) -> MemberRead:
    membership = await get_membership(workspace_id, current.id)
    require_role(membership, *MANAGERS)

    user = await directory.find_by_email(payload.email, current.token)
    if user is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No user with this email")
    if await Membership.exists(workspace_id=workspace_id, user_id=user.id):
        raise HTTPException(status.HTTP_409_CONFLICT, "User is already a member")

    new_member = await Membership.create(
        workspace_id=workspace_id,
        user_id=user.id,
        user_email=user.email,
        user_full_name=user.full_name,
        role=payload.role,
    )
    await publisher.publish(
        "workspace.member_added",
        {"workspace_id": workspace_id, "user_id": user.id, "role": payload.role.value},
        actor_id=current.id,
    )
    return to_member_read(new_member)


@router.get("/{workspace_id}/members/{user_id}", response_model=MemberRead)
async def read_member(workspace_id: int, user_id: int, current: AuthenticatedUser) -> MemberRead:
    """Membership check used by TaskService and AnalyticsService (REST, token forwarded)."""
    await get_membership(workspace_id, current.id)
    target = await Membership.get_or_none(workspace_id=workspace_id, user_id=user_id)
    if target is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Member not found")
    return to_member_read(target)


@router.delete("/{workspace_id}/members/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_member(
    workspace_id: int, user_id: int, current: AuthenticatedUser, publisher: Publisher
) -> Response:
    membership = await get_membership(workspace_id, current.id)
    if user_id != current.id:  # anyone may leave, only managers may remove others
        require_role(membership, *MANAGERS)
    target = await Membership.get_or_none(workspace_id=workspace_id, user_id=user_id)
    if target is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Member not found")
    if target.role == Role.OWNER:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "The owner cannot be removed")
    await target.delete()
    await publisher.publish(
        "workspace.member_removed",
        {"workspace_id": workspace_id, "user_id": user_id},
        actor_id=current.id,
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)
