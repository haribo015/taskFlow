from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status

from app.clients import WorkspaceDirectory, get_workspace_directory
from app.messaging import EventPublisher, get_publisher
from app.models import Task, TaskPriority, TaskStatus
from app.schemas import TaskCreate, TaskRead, TaskUpdate, task_event_data
from app.security import AuthenticatedUser, CurrentUser

router = APIRouter(prefix="/api/tasks", tags=["tasks"])

Publisher = Annotated[EventPublisher, Depends(get_publisher)]
Directory = Annotated[WorkspaceDirectory, Depends(get_workspace_directory)]


async def ensure_member(
    directory: WorkspaceDirectory, workspace_id: int, user: CurrentUser
) -> None:
    if await directory.get_membership(workspace_id, user.id, user.token) is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Workspace not found")


async def ensure_assignable(
    directory: WorkspaceDirectory, workspace_id: int, assignee_id: int | None, user: CurrentUser
) -> None:
    if assignee_id is None or assignee_id == user.id:
        return
    if await directory.get_membership(workspace_id, assignee_id, user.token) is None:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT, "Assignee is not a member of the workspace"
        )


async def get_task_for_member(
    task_id: int, directory: WorkspaceDirectory, user: CurrentUser
) -> Task:
    task = await Task.get_or_none(id=task_id)
    if task is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Task not found")
    await ensure_member(directory, task.workspace_id, user)
    return task


def apply_status(task: Task, new_status: TaskStatus) -> None:
    if new_status == TaskStatus.DONE and task.status != TaskStatus.DONE:
        task.completed_at = datetime.now(UTC)
    elif new_status != TaskStatus.DONE:
        task.completed_at = None
    task.status = new_status


@router.post("", response_model=TaskRead, status_code=status.HTTP_201_CREATED)
async def create_task(
    payload: TaskCreate, current: AuthenticatedUser, directory: Directory, publisher: Publisher
) -> Task:
    await ensure_member(directory, payload.workspace_id, current)
    await ensure_assignable(directory, payload.workspace_id, payload.assignee_id, current)
    task = Task(
        workspace_id=payload.workspace_id,
        title=payload.title.strip(),
        description=payload.description,
        priority=payload.priority,
        assignee_id=payload.assignee_id,
        due_date=payload.due_date,
        created_by=current.id,
    )
    apply_status(task, payload.status)
    await task.save()
    await publisher.publish("task.created", task_event_data(task), actor_id=current.id)
    return task


@router.get("", response_model=list[TaskRead])
async def list_tasks(
    current: AuthenticatedUser,
    directory: Directory,
    workspace_id: Annotated[int, Query()],
    status_filter: Annotated[TaskStatus | None, Query(alias="status")] = None,
    priority: Annotated[TaskPriority | None, Query()] = None,
    assignee_id: Annotated[int | None, Query()] = None,
) -> list[Task]:
    await ensure_member(directory, workspace_id, current)
    query = Task.filter(workspace_id=workspace_id)
    if status_filter is not None:
        query = query.filter(status=status_filter)
    if priority is not None:
        query = query.filter(priority=priority)
    if assignee_id is not None:
        query = query.filter(assignee_id=assignee_id)
    return await query


@router.get("/mine", response_model=list[TaskRead])
async def list_my_tasks(
    current: AuthenticatedUser,
    status_filter: Annotated[TaskStatus | None, Query(alias="status")] = None,
) -> list[Task]:
    query = Task.filter(assignee_id=current.id)
    if status_filter is not None:
        query = query.filter(status=status_filter)
    return await query


@router.get("/{task_id}", response_model=TaskRead)
async def read_task(task_id: int, current: AuthenticatedUser, directory: Directory) -> Task:
    return await get_task_for_member(task_id, directory, current)


@router.patch("/{task_id}", response_model=TaskRead)
async def update_task(
    task_id: int,
    payload: TaskUpdate,
    current: AuthenticatedUser,
    directory: Directory,
    publisher: Publisher,
) -> Task:
    task = await get_task_for_member(task_id, directory, current)
    changes = payload.model_dump(exclude_unset=True)

    if "assignee_id" in changes:
        await ensure_assignable(directory, task.workspace_id, changes["assignee_id"], current)
        task.assignee_id = changes["assignee_id"]
    if "due_date" in changes:
        task.due_date = changes["due_date"]
    for field in ("title", "description", "priority"):
        if changes.get(field) is not None:
            setattr(task, field, changes[field])
    if changes.get("status") is not None:
        apply_status(task, changes["status"])

    await task.save()
    await publisher.publish("task.updated", task_event_data(task), actor_id=current.id)
    return task


@router.delete("/{task_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_task(
    task_id: int, current: AuthenticatedUser, directory: Directory, publisher: Publisher
) -> Response:
    task = await get_task_for_member(task_id, directory, current)
    data = task_event_data(task)
    await task.delete()
    await publisher.publish("task.deleted", data, actor_id=current.id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
