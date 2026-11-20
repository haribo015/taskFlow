from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta
from typing import Any

import jwt
import pytest
from httpx import ASGITransport, AsyncClient
from tortoise.contrib.fastapi import RegisterTortoise

from app.clients import UserInfo, get_user_directory
from app.config import Settings, get_settings
from app.main import MODELS, create_app
from app.messaging import get_publisher

TEST_SETTINGS = Settings(
    database_url="sqlite://:memory:", jwt_secret="test-secret-with-at-least-32-bytes!!"
)

USERS = {
    1: UserInfo(id=1, email="alice@example.com", full_name="Alice"),
    2: UserInfo(id=2, email="bob@example.com", full_name="Bob"),
    3: UserInfo(id=3, email="carol@example.com", full_name="Carol"),
}


def auth(user_id: int) -> dict[str, str]:
    user = USERS[user_id]
    now = datetime.now(UTC)
    token = jwt.encode(
        {
            "sub": str(user.id),
            "email": user.email,
            "name": user.full_name,
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


class FakeUserDirectory:
    async def find_by_email(self, email: str, token: str) -> UserInfo | None:
        return next((u for u in USERS.values() if u.email == email.lower()), None)


@pytest.fixture
def publisher() -> FakePublisher:
    return FakePublisher()


@pytest.fixture
async def client(publisher: FakePublisher) -> AsyncIterator[AsyncClient]:
    app = create_app(TEST_SETTINGS, init_resources=False)
    app.dependency_overrides[get_settings] = lambda: TEST_SETTINGS
    app.dependency_overrides[get_publisher] = lambda: publisher
    app.dependency_overrides[get_user_directory] = FakeUserDirectory
    async with RegisterTortoise(
        db_url=TEST_SETTINGS.database_url, modules=MODELS, generate_schemas=True
    ):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            yield ac
