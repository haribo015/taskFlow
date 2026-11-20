"""REST client towards UserService."""

from dataclasses import dataclass

import httpx
from fastapi import HTTPException, Request, status


@dataclass(frozen=True)
class UserInfo:
    id: int
    email: str
    full_name: str


class UserDirectory:
    def __init__(self, http: httpx.AsyncClient) -> None:
        self._http = http

    async def find_by_email(self, email: str, token: str) -> UserInfo | None:
        try:
            response = await self._http.get(
                "/api/users/lookup",
                params={"email": email},
                headers={"Authorization": f"Bearer {token}"},
            )
        except httpx.HTTPError as exc:
            raise HTTPException(
                status.HTTP_503_SERVICE_UNAVAILABLE, "UserService unavailable"
            ) from exc
        if response.status_code == status.HTTP_404_NOT_FOUND:
            return None
        if response.is_error:
            raise HTTPException(status.HTTP_502_BAD_GATEWAY, "UserService error")
        body = response.json()
        return UserInfo(id=body["id"], email=body["email"], full_name=body["full_name"])


def get_user_directory(request: Request) -> UserDirectory:
    return request.app.state.user_directory
