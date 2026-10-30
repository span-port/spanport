from datetime import UTC, datetime, timedelta

import pytest
from fakes import FakeSessionStore, FakeUserStore

from spanport_server.core.errors import (
    CsrfError,
    InvalidLoginError,
    InvalidRequestError,
    NotFoundError,
    NotSignedInError,
    SetupLinkError,
)
from spanport_server.core.passwords import hash_password
from spanport_server.schemas.auth import LoginRequest, Role, SetupRequest, SignedIn
from spanport_server.services.auth_service import AuthService

pytestmark = pytest.mark.anyio

PASSWORD = "a long enough passphrase"


class Clock:
    """A clock tests can move forward."""

    def __init__(self) -> None:
        self.now = datetime.now(UTC)

    def __call__(self) -> datetime:
        return self.now


def make_service() -> tuple[AuthService, FakeUserStore, FakeSessionStore, Clock]:
    users, sessions, clock = FakeUserStore(), FakeSessionStore(), Clock()
    return AuthService(users, sessions, now=clock), users, sessions, clock


def setup_form(token: str, **overrides: str) -> SetupRequest:
    fields = {
        "token": token,
        "name": "Nitish",
        "email": "Owner@Example.com",
        "password": PASSWORD,
        "organization": "Divami Design Labs",
    }
    return SetupRequest.model_validate(fields | overrides)


async def new_token(service: AuthService) -> str:
    token = await service.issue_setup_token()
    assert token is not None
    return token


async def signed_in_owner() -> tuple[AuthService, FakeUserStore, FakeSessionStore, Clock, SignedIn]:
    service, users, sessions, clock = make_service()
    token = await new_token(service)
    return service, users, sessions, clock, await service.complete_setup(setup_form(token))


async def test_setup_token_is_issued_only_while_nobody_can_sign_in() -> None:
    service, users, _, _ = make_service()

    token = await new_token(service)
    users.add_user("someone@example.com", hash_password(PASSWORD))

    assert len(token) >= 32
    assert token not in users.setup_tokens
    assert await service.issue_setup_token() is None


async def test_setup_creates_the_owner_and_signs_them_in() -> None:
    _, users, sessions, _, signed_in = await signed_in_owner()

    owner = signed_in.user
    assert (owner.email, owner.role, owner.org_slug) == (
        "owner@example.com",
        Role.OWNER,
        "divami-design-labs",
    )
    assert signed_in.session_token not in sessions.sessions
    assert len(sessions.sessions) == 1
    stored_hash = users.users[owner.id][1]
    assert PASSWORD not in stored_hash


async def test_setup_token_works_once_and_expires_after_an_hour() -> None:
    service, _, _, clock = make_service()
    late_token = await new_token(service)
    clock.now += timedelta(hours=1, seconds=1)

    with pytest.raises(SetupLinkError):
        await service.complete_setup(setup_form(late_token))
    with pytest.raises(SetupLinkError):
        await service.complete_setup(setup_form("made-up-token"))

    fresh_token = await new_token(service)
    await service.complete_setup(setup_form(fresh_token))
    with pytest.raises(SetupLinkError, match="already set up"):
        await service.complete_setup(setup_form(fresh_token))


async def test_setup_refuses_weak_passwords_and_nameless_organizations() -> None:
    service, _, _, _ = make_service()
    token = await new_token(service)

    with pytest.raises(InvalidRequestError, match="at least 12"):
        await service.complete_setup(setup_form(token, password="short"))
    with pytest.raises(InvalidRequestError, match="organization"):
        await service.complete_setup(setup_form(token, organization="!!!"))


async def test_login_signs_in_with_the_right_password_only(
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level("INFO")
    service, _, _, _, _ = await signed_in_owner()

    signed_in = await service.login(LoginRequest(email="OWNER@example.com", password=PASSWORD))
    with pytest.raises(InvalidLoginError) as wrong_password:
        await service.login(LoginRequest(email="owner@example.com", password="wrong password!!"))
    with pytest.raises(InvalidLoginError) as unknown_email:
        await service.login(LoginRequest(email="nobody@example.com", password=PASSWORD))

    assert signed_in.user.role == Role.OWNER
    assert wrong_password.value.detail == unknown_email.value.detail
    assert "nobody@example.com" not in caplog.text
    assert PASSWORD not in caplog.text


async def test_session_needs_its_csrf_token_for_changes() -> None:
    service, _, _, _, signed_in = await signed_in_owner()
    token, csrf = signed_in.session_token, signed_in.csrf_token

    reading = await service.authenticate(token, None, needs_csrf=False)
    changing = await service.authenticate(token, csrf, needs_csrf=True)

    assert reading == changing == signed_in.user
    with pytest.raises(CsrfError):
        await service.authenticate(token, None, needs_csrf=True)
    with pytest.raises(CsrfError):
        await service.authenticate(token, "forged", needs_csrf=True)


async def test_no_cookie_unknown_session_or_idle_session_is_not_signed_in() -> None:
    service, _, _, clock, signed_in = await signed_in_owner()

    with pytest.raises(NotSignedInError):
        await service.authenticate(None, None, needs_csrf=False)
    with pytest.raises(NotSignedInError):
        await service.authenticate("made-up", None, needs_csrf=False)

    clock.now += timedelta(hours=8, seconds=1)
    with pytest.raises(NotSignedInError):
        await service.authenticate(signed_in.session_token, None, needs_csrf=False)


async def test_activity_keeps_a_session_alive() -> None:
    service, _, _, clock, signed_in = await signed_in_owner()

    for _ in range(3):
        clock.now += timedelta(hours=7)
        await service.authenticate(signed_in.session_token, None, needs_csrf=False)


async def test_logout_ends_the_session_immediately() -> None:
    service, _, _, _, signed_in = await signed_in_owner()

    await service.logout(signed_in.session_token)

    with pytest.raises(NotSignedInError):
        await service.authenticate(signed_in.session_token, None, needs_csrf=False)


async def test_password_reset_changes_the_password_and_signs_out_everywhere() -> None:
    service, _, _, _, signed_in = await signed_in_owner()
    new_password = "another long passphrase"

    await service.reset_password("Owner@example.com", new_password)

    with pytest.raises(NotSignedInError):
        await service.authenticate(signed_in.session_token, None, needs_csrf=False)
    with pytest.raises(InvalidLoginError):
        await service.login(LoginRequest(email="owner@example.com", password=PASSWORD))
    await service.login(LoginRequest(email="owner@example.com", password=new_password))
    with pytest.raises(NotFoundError):
        await service.reset_password("nobody@example.com", new_password)
    with pytest.raises(InvalidRequestError):
        await service.reset_password("owner@example.com", "short")
