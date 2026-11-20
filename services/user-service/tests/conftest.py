from collections.abc import AsyncIterator

import pytest
from httpx import ASGITransport, AsyncClient
from tortoise.contrib.fastapi import RegisterTortoise

from app.config import Settings, get_settings
from app.main import MODELS, create_app

TEST_SETTINGS = Settings(
    database_url="sqlite://:memory:", jwt_secret="test-secret-with-at-least-32-bytes!!"
)


@pytest.fixture
async def client() -> AsyncIterator[AsyncClient]:
    app = create_app(TEST_SETTINGS, init_db=False)
    app.dependency_overrides[get_settings] = lambda: TEST_SETTINGS
    async with RegisterTortoise(
        db_url=TEST_SETTINGS.database_url, modules=MODELS, generate_schemas=True
    ):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            yield ac


async def register_and_login(
    client: AsyncClient, email: str = "alice@example.com", password: str = "secret123"
) -> dict:
    await client.post(
        "/api/auth/register",
        json={"email": email, "full_name": "Alice", "password": password},
    )
    response = await client.post("/api/auth/login", json={"email": email, "password": password})
    return response.json()
