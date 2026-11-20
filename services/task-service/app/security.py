"""JWT verification. Tokens are issued by UserService and signed with the shared secret."""

from dataclasses import dataclass
from typing import Annotated

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.config import Settings, get_settings

bearer_scheme = HTTPBearer(auto_error=False)


@dataclass(frozen=True)
class CurrentUser:
    id: int
    email: str
    full_name: str
    token: str


def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> CurrentUser:
    unauthorized = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or missing authentication token",
        headers={"WWW-Authenticate": "Bearer"},
    )
    if credentials is None:
        raise unauthorized
    try:
        payload = jwt.decode(
            credentials.credentials,
            settings.jwt_secret,
            algorithms=[settings.jwt_algorithm],
            issuer="taskflow-user-service",
        )
        return CurrentUser(
            id=int(payload["sub"]),
            email=payload["email"],
            full_name=payload.get("name", ""),
            token=credentials.credentials,
        )
    except (jwt.PyJWTError, KeyError, ValueError) as exc:
        raise unauthorized from exc


AuthenticatedUser = Annotated[CurrentUser, Depends(get_current_user)]
