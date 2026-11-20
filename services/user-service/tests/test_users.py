import jwt
from httpx import AsyncClient

from app.passwords import hash_password, verify_password
from tests.conftest import TEST_SETTINGS, register_and_login


async def test_health(client: AsyncClient) -> None:
    response = await client.get("/health")
    assert response.status_code == 200
    assert response.json()["service"] == "user-service"


async def test_register_returns_user_without_password(client: AsyncClient) -> None:
    response = await client.post(
        "/api/auth/register",
        json={"email": "Bob@Example.com", "full_name": "Bob", "password": "secret123"},
    )
    assert response.status_code == 201
    body = response.json()
    assert body["email"] == "bob@example.com"
    assert "password" not in body and "password_hash" not in body


async def test_register_duplicate_email_conflicts(client: AsyncClient) -> None:
    payload = {"email": "bob@example.com", "full_name": "Bob", "password": "secret123"}
    await client.post("/api/auth/register", json=payload)
    response = await client.post("/api/auth/register", json=payload)
    assert response.status_code == 409


async def test_register_rejects_short_password(client: AsyncClient) -> None:
    response = await client.post(
        "/api/auth/register",
        json={"email": "bob@example.com", "full_name": "Bob", "password": "short"},
    )
    assert response.status_code == 422


async def test_login_issues_jwt_with_identity_claims(client: AsyncClient) -> None:
    body = await register_and_login(client)
    claims = jwt.decode(
        body["access_token"],
        TEST_SETTINGS.jwt_secret,
        algorithms=["HS256"],
        issuer="taskflow-user-service",
    )
    assert claims["email"] == "alice@example.com"
    assert claims["sub"] == str(body["user"]["id"])
    assert body["token_type"] == "bearer"


async def test_login_wrong_password(client: AsyncClient) -> None:
    await register_and_login(client)
    response = await client.post(
        "/api/auth/login", json={"email": "alice@example.com", "password": "wrongpass"}
    )
    assert response.status_code == 401


async def test_me_requires_token(client: AsyncClient) -> None:
    assert (await client.get("/api/users/me")).status_code == 401
    response = await client.get("/api/users/me", headers={"Authorization": "Bearer garbage"})
    assert response.status_code == 401


async def test_me_and_update(client: AsyncClient) -> None:
    token = (await register_and_login(client))["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    response = await client.patch("/api/users/me", json={"full_name": "Alice B."}, headers=headers)
    assert response.status_code == 200
    assert response.json()["full_name"] == "Alice B."

    me = await client.get("/api/users/me", headers=headers)
    assert me.json()["full_name"] == "Alice B."


async def test_lookup_by_email_and_by_id(client: AsyncClient) -> None:
    token = (await register_and_login(client))["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    await client.post(
        "/api/auth/register",
        json={"email": "carol@example.com", "full_name": "Carol", "password": "secret123"},
    )

    found = await client.get("/api/users/lookup?email=CAROL@example.com", headers=headers)
    assert found.status_code == 200
    carol_id = found.json()["id"]

    by_id = await client.get(f"/api/users/{carol_id}", headers=headers)
    assert by_id.json()["email"] == "carol@example.com"

    missing = await client.get("/api/users/lookup?email=nobody@example.com", headers=headers)
    assert missing.status_code == 404


def test_password_hashing_roundtrip() -> None:
    encoded = hash_password("secret123", iterations=1_000)
    assert verify_password("secret123", encoded)
    assert not verify_password("other-password", encoded)
    assert not verify_password("secret123", "not-a-valid-hash")
