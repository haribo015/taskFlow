from httpx import AsyncClient

from tests.conftest import FakePublisher, auth


async def create_workspace(client: AsyncClient, owner: int = 1, name: str = "Projet") -> dict:
    response = await client.post(
        "/api/workspaces", json={"name": name, "description": "desc"}, headers=auth(owner)
    )
    assert response.status_code == 201, response.text
    return response.json()


async def test_health(client: AsyncClient) -> None:
    assert (await client.get("/health")).json()["service"] == "workspace-service"


async def test_requires_authentication(client: AsyncClient) -> None:
    assert (await client.get("/api/workspaces")).status_code == 401


async def test_create_workspace_makes_creator_owner(
    client: AsyncClient, publisher: FakePublisher
) -> None:
    workspace = await create_workspace(client)
    assert workspace["my_role"] == "owner"
    assert workspace["member_count"] == 1
    assert publisher.events[0][0] == "workspace.created"

    listing = await client.get("/api/workspaces", headers=auth(1))
    assert [w["id"] for w in listing.json()] == [workspace["id"]]


async def test_non_member_cannot_see_workspace(client: AsyncClient) -> None:
    workspace = await create_workspace(client)
    response = await client.get(f"/api/workspaces/{workspace['id']}", headers=auth(2))
    assert response.status_code == 404
    assert (await client.get("/api/workspaces", headers=auth(2))).json() == []


async def test_add_member_resolves_user_through_user_service(
    client: AsyncClient, publisher: FakePublisher
) -> None:
    wid = (await create_workspace(client))["id"]
    response = await client.post(
        f"/api/workspaces/{wid}/members", json={"email": "BOB@example.com"}, headers=auth(1)
    )
    assert response.status_code == 201
    assert response.json() == {
        **response.json(),
        "user_id": 2,
        "full_name": "Bob",
        "role": "member",
    }
    assert publisher.events[-1][0] == "workspace.member_added"

    members = await client.get(f"/api/workspaces/{wid}/members", headers=auth(2))
    assert {m["user_id"] for m in members.json()} == {1, 2}


async def test_add_member_errors(client: AsyncClient) -> None:
    wid = (await create_workspace(client))["id"]
    url = f"/api/workspaces/{wid}/members"

    unknown = await client.post(url, json={"email": "nobody@example.com"}, headers=auth(1))
    assert unknown.status_code == 404

    await client.post(url, json={"email": "bob@example.com"}, headers=auth(1))
    duplicate = await client.post(url, json={"email": "bob@example.com"}, headers=auth(1))
    assert duplicate.status_code == 409

    # a plain member cannot invite
    forbidden = await client.post(url, json={"email": "carol@example.com"}, headers=auth(2))
    assert forbidden.status_code == 403

    # the owner role cannot be granted through invitation
    invalid = await client.post(
        url, json={"email": "carol@example.com", "role": "owner"}, headers=auth(1)
    )
    assert invalid.status_code == 422


async def test_membership_check_endpoint(client: AsyncClient) -> None:
    wid = (await create_workspace(client))["id"]
    await client.post(
        f"/api/workspaces/{wid}/members",
        json={"email": "bob@example.com", "role": "admin"},
        headers=auth(1),
    )
    ok = await client.get(f"/api/workspaces/{wid}/members/2", headers=auth(1))
    assert ok.status_code == 200 and ok.json()["role"] == "admin"

    missing = await client.get(f"/api/workspaces/{wid}/members/3", headers=auth(1))
    assert missing.status_code == 404

    outsider = await client.get(f"/api/workspaces/{wid}/members/1", headers=auth(3))
    assert outsider.status_code == 404


async def test_update_and_delete_permissions(client: AsyncClient, publisher: FakePublisher) -> None:
    wid = (await create_workspace(client))["id"]
    await client.post(
        f"/api/workspaces/{wid}/members",
        json={"email": "bob@example.com", "role": "admin"},
        headers=auth(1),
    )

    renamed = await client.patch(
        f"/api/workspaces/{wid}", json={"name": "Nouveau"}, headers=auth(2)
    )
    assert renamed.status_code == 200 and renamed.json()["name"] == "Nouveau"

    assert (await client.delete(f"/api/workspaces/{wid}", headers=auth(2))).status_code == 403
    assert (await client.delete(f"/api/workspaces/{wid}", headers=auth(1))).status_code == 204
    assert publisher.events[-1] == ("workspace.deleted", {"workspace_id": wid})
    assert (await client.get(f"/api/workspaces/{wid}", headers=auth(1))).status_code == 404


async def test_remove_member_rules(client: AsyncClient) -> None:
    wid = (await create_workspace(client))["id"]
    for email in ("bob@example.com", "carol@example.com"):
        await client.post(f"/api/workspaces/{wid}/members", json={"email": email}, headers=auth(1))

    # members cannot remove others, but can leave
    assert (
        await client.delete(f"/api/workspaces/{wid}/members/3", headers=auth(2))
    ).status_code == 403
    assert (
        await client.delete(f"/api/workspaces/{wid}/members/2", headers=auth(2))
    ).status_code == 204
    # the owner cannot be removed
    assert (
        await client.delete(f"/api/workspaces/{wid}/members/1", headers=auth(1))
    ).status_code == 400
    assert (
        await client.delete(f"/api/workspaces/{wid}/members/3", headers=auth(1))
    ).status_code == 204
