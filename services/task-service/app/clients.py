"""REST client towards WorkspaceService (membership checks)."""

from dataclasses import dataclass

import httpx
from fastapi import HTTPException, Request, status


@dataclass(frozen=True)
class MemberInfo:
    user_id: int
    role: str


class WorkspaceDirectory:
    def __init__(self, http: httpx.AsyncClient) -> None:
        self._http = http

    async def get_membership(
        self, workspace_id: int, user_id: int, token: str
    ) -> MemberInfo | None:
        """Return ``user_id``'s membership, or None if the caller or the user is not a member."""
        try:
            response = await self._http.get(
                f"/api/workspaces/{workspace_id}/members/{user_id}",
                headers={"Authorization": f"Bearer {token}"},
            )
        except httpx.HTTPError as exc:
            raise HTTPException(
                status.HTTP_503_SERVICE_UNAVAILABLE, "WorkspaceService unavailable"
            ) from exc
        if response.status_code == status.HTTP_404_NOT_FOUND:
            return None
        if response.is_error:
            raise HTTPException(status.HTTP_502_BAD_GATEWAY, "WorkspaceService error")
        body = response.json()
        return MemberInfo(user_id=body["user_id"], role=body["role"])


def get_workspace_directory(request: Request) -> WorkspaceDirectory:
    return request.app.state.workspace_directory
