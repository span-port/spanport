from collections.abc import AsyncIterator

import httpx
import pytest
from fakes import FakeSessionStore, FakeTeamStore, FakeUserStore

from spanport_server.core.passwords import hash_password
from spanport_server.dependencies import get_auth_service, get_team_service
from spanport_server.main import create_app
from spanport_server.schemas.auth import Role
from spanport_server.services.auth_service import AuthService
from spanport_server.services.team_service import TeamService

pytestmark = pytest.mark.anyio

PASSWORD = "a long enough passphrase"


@pytest.fixture
async def client() -> AsyncIterator[httpx.AsyncClient]:
    users = FakeUserStore()
    owner = users.add_user("owner@example.com", hash_password(PASSWORD), Role.OWNER)
    users.add_user("member@example.com", hash_password(PASSWORD), Role.MEMBER, org_id=owner.org_id)
    sessions = FakeSessionStore()
    auth = AuthService(users, sessions)
    team = TeamService(FakeTeamStore(users), sessions)
    app = create_app()
    app.dependency_overrides[get_auth_service] = lambda: auth
    app.dependency_overrides[get_team_service] = lambda: team
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="https://test") as http:
        yield http


async def sign_in(client: httpx.AsyncClient, email: str) -> dict[str, str]:
    response = await client.post("/api/v1/auth/login", json={"email": email, "password": PASSWORD})
    assert response.status_code == 200
    return {"X-CSRF-Token": client.cookies["__Host-sp_csrf"]}


async def test_owner_invites_and_the_person_accepts_and_is_signed_in(
    client: httpx.AsyncClient,
) -> None:
    csrf = await sign_in(client, "owner@example.com")
    created = await client.post(
        "/api/v1/invites", json={"email": "new@example.com", "role": "viewer"}, headers=csrf
    )
    token = created.json()["token"]
    client.cookies.clear()

    inspected = await client.post("/api/v1/invites/inspect", json={"token": token})
    accepted = await client.post(
        "/api/v1/invites/accept", json={"token": token, "name": "New", "password": PASSWORD}
    )
    me = await client.get("/api/v1/auth/me")

    assert created.status_code == 201
    assert inspected.json()["email"] == "new@example.com"
    assert accepted.status_code == 201
    assert (me.json()["email"], me.json()["role"]) == ("new@example.com", "viewer")


async def test_a_bad_invite_link_is_gone(client: httpx.AsyncClient) -> None:
    response = await client.post("/api/v1/invites/inspect", json={"token": "nope"})

    assert response.status_code == 410
    assert response.json()["code"] == "invite_invalid"


async def test_members_cannot_see_or_invite_users(client: httpx.AsyncClient) -> None:
    csrf = await sign_in(client, "member@example.com")

    listing = await client.get("/api/v1/users")
    invite = await client.post(
        "/api/v1/invites", json={"email": "x@example.com", "role": "member"}, headers=csrf
    )

    assert listing.status_code == 403
    assert invite.status_code == 403
