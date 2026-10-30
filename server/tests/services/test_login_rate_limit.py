from datetime import UTC, datetime, timedelta

import pytest
from fakes import FakeSessionStore, FakeUserStore

from spanport_server.core.errors import InvalidLoginError, RateLimitedError
from spanport_server.core.passwords import hash_password
from spanport_server.schemas.auth import LoginRequest, Role
from spanport_server.services.auth_service import AuthService

pytestmark = pytest.mark.anyio

PASSWORD = "a long enough passphrase"
START = datetime(2026, 10, 30, 12, 0, tzinfo=UTC)


class Setup:
    def __init__(self) -> None:
        self.now = START
        self.users = FakeUserStore()
        self.users.add_user("sam@example.com", hash_password(PASSWORD), Role.OWNER)
        self.auth = AuthService(self.users, FakeSessionStore(), lambda: self.now)

    async def wrong(self, times: int, email: str = "sam@example.com") -> None:
        for _ in range(times):
            with pytest.raises(InvalidLoginError):
                await self.auth.login(LoginRequest(email=email, password="wrong password!!"))
            self.now += timedelta(minutes=1)

    async def right(self, email: str = "Sam@Example.com") -> None:
        await self.auth.login(LoginRequest(email=email, password=PASSWORD))


@pytest.fixture
def setup() -> Setup:
    return Setup()


async def test_five_wrong_passwords_lock_the_email_even_for_the_right_one(setup: Setup) -> None:
    await setup.wrong(5)

    with pytest.raises(RateLimitedError) as locked:
        await setup.right()

    # Failures at 12:00..12:04; the oldest leaves the 15-minute window at 12:15, it is now 12:05.
    assert locked.value.retry_after_seconds == 10 * 60
    assert "Try again in 10 min." in locked.value.detail


async def test_the_lock_lifts_when_the_window_has_passed(setup: Setup) -> None:
    await setup.wrong(5)
    setup.now = START + timedelta(minutes=15)

    await setup.right()


async def test_a_successful_sign_in_resets_the_count(setup: Setup) -> None:
    await setup.wrong(4)
    await setup.right()
    await setup.wrong(4)

    await setup.right()


async def test_unknown_emails_are_limited_too_and_other_emails_are_not(setup: Setup) -> None:
    await setup.wrong(5, email="nobody@example.com")

    with pytest.raises(RateLimitedError):
        await setup.auth.login(LoginRequest(email="nobody@example.com", password=PASSWORD))
    await setup.right()
