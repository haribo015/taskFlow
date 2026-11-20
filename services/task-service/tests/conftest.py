from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta
from typing import Any

import jwt
import pytest
from httpx import ASGITransport, AsyncClient
from tortoise.contrib.fastapi import RegisterTortoise

from app.clients import MemberInfo, get_workspace_directory
from app.config import Settings, get_settings
from app.main import MODELS, create_app
from app.messaging import get_publisher

TEST_SETTINGS = Settings(
    database_url="sqlite://:memory:", jwt_secret="test-secret-with-at-least-32-bytes!!"
)

# workspace 10: users 1 and 2 -- workspace 20: user 3 only
MEMBERSHIPS = {10: {1, 2}, 20: {3}}


def auth(user_id: int) -> dict[str, str]:
    now = datetime.now(UTC)
    token = jwt.encode(
        {
            "sub": str(user_id),
            "email": f"user{user_id}@example.com",
            "name": f"User {user_id}",
            "iat": now,
            "exp": now + timedelta(minutes=5),
            "iss": "taskflow-user-service",
        },
        TEST_SETTINGS.jwt_secret,
        algorithm="HS256",
    )
    return {"Authorization": f"Bearer {token}"}


class FakePublisher:
    def __init__(self) -> None:
        self.events: list[tuple[str, dict[str, Any]]] = []

    async def publish(
        self, routing_key: str, data: dict[str, Any], *, actor_id: int | None = None
    ) -> None:
        self.events.append((routing_key, data))


class FakeWorkspaceDirectory:
    async def get_membership(
        self, workspace_id: int, user_id: int, token: str
    ) -> MemberInfo | None:
        if user_id in MEMBERSHIPS.get(workspace_id, set()):
            return MemberInfo(user_id=user_id, role="member")
        return None


@pytest.fixture
def publisher() -> FakePublisher:
    return FakePublisher()


@pytest.fixture
async def client(publisher: FakePublisher) -> AsyncIterator[AsyncClient]:
    app = create_app(TEST_SETTINGS, init_resources=False)
    app.dependency_overrides[get_settings] = lambda: TEST_SETTINGS
    app.dependency_overrides[get_publisher] = lambda: publisher
    app.dependency_overrides[get_workspace_directory] = FakeWorkspaceDirectory
    async with RegisterTortoise(
        db_url=TEST_SETTINGS.database_url, modules=MODELS, generate_schemas=True
    ):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            yield ac
