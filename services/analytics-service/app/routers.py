from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from app import stats
from app.clients import WorkspaceDirectory, get_workspace_directory
from app.models import ActivityEvent, TaskSnapshot
from app.schemas import ActivityRead, MyStats, WorkspaceStats
from app.security import AuthenticatedUser

router = APIRouter(prefix="/api/analytics", tags=["analytics"])

Directory = Annotated[WorkspaceDirectory, Depends(get_workspace_directory)]


@router.get("/workspaces/{workspace_id}", response_model=WorkspaceStats)
async def workspace_stats(
    workspace_id: int, current: AuthenticatedUser, directory: Directory
) -> WorkspaceStats:
    if await directory.get_membership(workspace_id, current.id, current.token) is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Workspace not found")

    tasks = await TaskSnapshot.filter(workspace_id=workspace_id)
    activity = await ActivityEvent.filter(workspace_id=workspace_id).limit(15)
    now = stats.utcnow()
    return WorkspaceStats(
        workspace_id=workspace_id,
        total_tasks=len(tasks),
        by_status=stats.count_by(tasks, "status", stats.STATUSES),
        by_priority=stats.count_by(tasks, "priority", stats.PRIORITIES),
        completion_rate=stats.completion_rate(tasks),
        overdue_tasks=stats.overdue_count(tasks, now),
        completed_last_7_days=stats.completed_since(tasks, now),
        by_assignee=stats.by_assignee(tasks),
        recent_activity=[ActivityRead.model_validate(a) for a in activity],
    )


@router.get("/me", response_model=MyStats)
async def my_stats(current: AuthenticatedUser) -> MyStats:
    tasks = await TaskSnapshot.filter(assignee_id=current.id)
    now = stats.utcnow()
    return MyStats(
        total_assigned=len(tasks),
        by_status=stats.count_by(tasks, "status", stats.STATUSES),
        overdue_tasks=stats.overdue_count(tasks, now),
        completed_last_7_days=stats.completed_since(tasks, now),
        workspaces=len({t.workspace_id for t in tasks}),
    )
