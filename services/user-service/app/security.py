"""JWT issuing (UserService only) and verification (shared logic)."""

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
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


def create_access_token(
    *, user_id: int, email: str, full_name: str, settings: Settings
) -> tuple[str, int]:
    expires_in = settings.access_token_expire_minutes * 60
    now = datetime.now(UTC)
    payload = {
        "sub": str(user_id),
        "email": email,
        "name": full_name,
        "iat": now,
        "exp": now + timedelta(seconds=expires_in),
        "iss": "taskflow-user-service",
    }
    token = jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)
    return token, expires_in


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
