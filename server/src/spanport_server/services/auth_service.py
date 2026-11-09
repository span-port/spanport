"""First-time setup, email and password sign-in, and server-side sessions."""

import hmac
import logging
import math
import re
import secrets
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from typing import Protocol

from spanport_server.core.constants import (
    CSRF_DETAIL,
    DEFAULT_SESSION_MAX_HOURS,
    INVALID_INVITE_DETAIL,
    INVALID_LOGIN_DETAIL,
    INVALID_SETUP_DETAIL,
    MIN_PASSWORD_LENGTH,
    NOT_SIGNED_IN_DETAIL,
    ORG_NAME_DETAIL,
    SECONDS_PER_MINUTE,
    SESSION_IDLE_TIMEOUT,
    SESSION_TOKEN_BYTES,
    SETUP_DONE_DETAIL,
    SETUP_TOKEN_LIFETIME,
    SLUG_PATTERN,
    SLUG_SEPARATOR,
    SLUG_SEPARATOR_PATTERN,
    TOO_MANY_LOGINS_DETAIL,
    UNKNOWN_USER_DETAIL,
    WEAK_PASSWORD_DETAIL,
)
from spanport_server.core.errors import (
    CsrfError,
    InvalidLoginError,
    InvalidRequestError,
    InviteLinkError,
    NotFoundError,
    NotSignedInError,
    RateLimitedError,
    SetupLinkError,
)
from spanport_server.core.ids import UuidV7
from spanport_server.core.key_hashing import hash_api_key
from spanport_server.core.passwords import hash_password_in_thread, verify_password_in_thread
from spanport_server.schemas.auth import (
    LoginLimit,
    LoginRequest,
    SetupRequest,
    SignedIn,
    UserRecord,
)
from spanport_server.schemas.team import AcceptInviteRequest, InviteDetails

logger = logging.getLogger(__name__)


class UserStore(Protocol):
    """What the auth service needs from user storage."""

    async def count_users(self) -> int: ...

    async def insert_setup_token(self, token_hash: str, expires_at: datetime) -> None: ...

    async def expire_setup_tokens(self, now: datetime) -> int: ...

    async def setup_token_usable(self, token_hash: str, now: datetime) -> bool: ...

    async def create_owner(
        self,
        token_hash: str,
        now: datetime,
        org_slug: str,
        name: str,
        email: str,
        password_hash: str,
    ) -> UserRecord | None: ...

    async def find_for_login(self, email: str) -> tuple[UserRecord, str] | None: ...

    async def find_by_id(self, user_id: UuidV7) -> UserRecord | None: ...

    async def set_password(self, email: str, password_hash: str) -> UuidV7 | None: ...

    async def find_open_invite(self, token_hash: str, now: datetime) -> InviteDetails | None: ...

    async def accept_invite(
        self, token_hash: str, now: datetime, name: str, password_hash: str
    ) -> UserRecord | None: ...

    async def reserve_login_attempt(
        self, email_hash: str, now: datetime, since: datetime, max_failures: int
    ) -> list[datetime]: ...

    async def clear_login_failures(self, email_hash: str) -> None: ...


class SessionStore(Protocol):
    """What the auth service needs from session storage."""

    async def insert(self, user_id: UuidV7, token_hash: str, csrf_hash: str) -> None: ...

    async def touch_active(
        self, token_hash: str, idle_since: datetime, created_since: datetime, now: datetime
    ) -> tuple[UuidV7, str] | None: ...

    async def revoke(self, token_hash: str, now: datetime) -> UuidV7 | None: ...

    async def revoke_for_user(self, user_id: UuidV7, now: datetime) -> int: ...


def utc_now() -> datetime:
    """The current time in UTC."""
    return datetime.now(UTC)


def normalize_email(email: str) -> str:
    """Emails are compared and stored trimmed and lower case."""
    return email.strip().lower()


def org_slug_for(organization: str) -> str:
    """Turn an organization name into its slug, e.g. "Divami Design Labs" → "divami-design-labs".

    Raises:
        InvalidRequestError: The name has no letters or digits.
    """
    slug = re.sub(SLUG_SEPARATOR_PATTERN, SLUG_SEPARATOR, organization.lower()).strip(
        SLUG_SEPARATOR
    )
    if not re.fullmatch(SLUG_PATTERN, slug):
        raise InvalidRequestError(ORG_NAME_DETAIL)
    return slug


def check_password_strength(password: str) -> None:
    """Raise InvalidRequestError for a password that is too short."""
    if len(password) < MIN_PASSWORD_LENGTH:
        raise InvalidRequestError(WEAK_PASSWORD_DETAIL)


class AuthService:
    """Who is signed in. Raw session ids, CSRF and setup tokens are never stored or logged."""

    def __init__(
        self,
        users: UserStore,
        sessions: SessionStore,
        now: Callable[[], datetime] = utc_now,
        login_limit: LoginLimit | None = None,
        session_max_age: timedelta = timedelta(hours=DEFAULT_SESSION_MAX_HOURS),
    ) -> None:
        """Create the service.

        Args:
            users: User and setup token storage.
            sessions: Session storage.
            now: The clock; tests pass a fixed one.
            login_limit: The sign-in rate limit from the server's settings; the defaults
                when None.
            session_max_age: How long a session may last however active it is
                (SPANPORT_SESSION_MAX_HOURS).
        """
        self._users = users
        self._sessions = sessions
        self._now = now
        self._login_limit = login_limit or LoginLimit()
        self._session_max_age = session_max_age

    async def issue_setup_token(self) -> str | None:
        """Create a one-time setup token while no user exists yet.

        The person installing Spanport reads it from the server's log and pastes it into the
        UI's Set up page; the server never needs to know where the UI is.

        Returns:
            The raw token (valid 1 hour, single use; earlier unused tokens stop working), or
            None when setup is already done.
        """
        if await self._users.count_users():
            return None
        now = self._now()
        expired = await self._users.expire_setup_tokens(now)
        token = secrets.token_urlsafe(SESSION_TOKEN_BYTES)
        await self._users.insert_setup_token(hash_api_key(token), now + SETUP_TOKEN_LIFETIME)
        logger.info("setup token issued older_tokens_expired=%d", expired)
        return token

    async def complete_setup(self, request: SetupRequest) -> SignedIn:
        """Create the owner from the setup form and sign them in.

        Raises:
            InvalidRequestError: Weak password or an organization name without letters or digits.
            SetupLinkError: Setup is done, or the link is wrong, used or expired.
        """
        check_password_strength(request.password)
        org_slug = org_slug_for(request.organization)
        if await self._users.count_users():
            raise SetupLinkError(SETUP_DONE_DETAIL)
        token_hash, now = hash_api_key(request.token), self._now()
        # Checked before the slow password hash, so made-up tokens cost the server nothing.
        if not await self._users.setup_token_usable(token_hash, now):
            logger.warning("setup rejected: link wrong, used or expired")
            raise SetupLinkError(INVALID_SETUP_DETAIL)
        password_hash = await hash_password_in_thread(request.password)
        owner = await self._users.create_owner(
            token_hash,
            now,
            org_slug,
            request.name.strip(),
            normalize_email(request.email),
            password_hash,
        )
        if owner is None:
            logger.warning("setup rejected: link wrong, used or expired")
            raise SetupLinkError(INVALID_SETUP_DETAIL)
        logger.info("owner created user=%s org=%s", owner.id, owner.org_slug)
        return await self._start_session(owner)

    async def inspect_invite(self, token: str) -> InviteDetails:
        """What an invite link is for, so the person can check it before accepting.

        Raises:
            InviteLinkError: The link is wrong, used, cancelled or expired.
        """
        details = await self._users.find_open_invite(hash_api_key(token), self._now())
        if details is None:
            raise InviteLinkError(INVALID_INVITE_DETAIL)
        return details

    async def accept_invite(self, request: AcceptInviteRequest) -> SignedIn:
        """Accept an invite: create the account with the invite's email and role, sign in.

        Raises:
            InvalidRequestError: The password is too short.
            InviteLinkError: The link can't be used, or the email got an account meanwhile.
        """
        check_password_strength(request.password)
        token_hash, now = hash_api_key(request.token), self._now()
        # Checked before the slow password hash, so made-up links cost the server nothing.
        if await self._users.find_open_invite(token_hash, now) is None:
            logger.warning("invite rejected: link wrong, used, cancelled or expired")
            raise InviteLinkError(INVALID_INVITE_DETAIL)
        password_hash = await hash_password_in_thread(request.password)
        user = await self._users.accept_invite(token_hash, now, request.name.strip(), password_hash)
        if user is None:
            logger.warning("invite rejected: link wrong, used, cancelled or expired")
            raise InviteLinkError(INVALID_INVITE_DETAIL)
        logger.info("invite accepted user=%s org=%s role=%s", user.id, user.org_slug, user.role)
        return await self._start_session(user)

    async def login(self, request: LoginRequest) -> SignedIn:
        """Sign in with email and password.

        After the login limit's wrong passwords for one email within its window, that
        email is refused (even with the right password) until the window has passed, so a
        password can't be guessed by trying many. Unknown emails count too, so the answer
        doesn't reveal which emails exist.

        Raises:
            RateLimitedError: Too many recent wrong passwords for this email (429).
            InvalidLoginError: Unknown email, disabled user or wrong password (never says which).
        """
        email_hash = hash_api_key(normalize_email(request.email))
        await self._reserve_login_attempt(email_hash)
        found = await self._users.find_for_login(normalize_email(request.email))
        user, password_hash = found if found else (None, None)
        if user is None or not await verify_password_in_thread(password_hash, request.password):
            # The attempt was stored as a failure up front, so there is nothing more to record.
            logger.info("sign-in rejected: wrong email or password")
            raise InvalidLoginError(INVALID_LOGIN_DETAIL)
        await self._users.clear_login_failures(email_hash)
        logger.info("signed in user=%s org=%s role=%s", user.id, user.org_slug, user.role)
        return await self._start_session(user)

    async def _reserve_login_attempt(self, email_hash: str) -> None:
        """Count this attempt as a failure until it succeeds, or refuse it while this email has
        too many recent wrong passwords.
        """
        limit, now = self._login_limit, self._now()
        failures = await self._users.reserve_login_attempt(
            email_hash, now, now - limit.window, limit.failures
        )
        if len(failures) < limit.failures:
            return
        # The lock lifts once the oldest of the last `limit.failures` failures leaves the window.
        retry_after = failures[-limit.failures] + limit.window - now
        seconds = max(1, math.ceil(retry_after.total_seconds()))
        minutes = math.ceil(seconds / SECONDS_PER_MINUTE)
        logger.warning("sign-in rate limited failures=%d retry_after_s=%d", len(failures), seconds)
        raise RateLimitedError(TOO_MANY_LOGINS_DETAIL.format(minutes=minutes), seconds)

    async def authenticate(
        self, session_token: str | None, csrf_token: str | None, needs_csrf: bool
    ) -> UserRecord:
        """The signed-in user for a request, keeping their session alive.

        Args:
            session_token: The session cookie, if any.
            csrf_token: The CSRF header, if any.
            needs_csrf: True for requests that may change something (anything but GET).

        Raises:
            NotSignedInError: No cookie, or the session is revoked, idle too long, older than
                the maximum session age or its user was disabled.
            CsrfError: The request needs a CSRF token and its header doesn't match the session.
        """
        if not session_token:
            raise NotSignedInError(NOT_SIGNED_IN_DETAIL)
        now = self._now()
        active = await self._sessions.touch_active(
            hash_api_key(session_token),
            now - SESSION_IDLE_TIMEOUT,
            now - self._session_max_age,
            now,
        )
        user = await self._users.find_by_id(active[0]) if active else None
        if active is None or user is None:
            raise NotSignedInError(NOT_SIGNED_IN_DETAIL)
        if needs_csrf and not hmac.compare_digest(hash_api_key(csrf_token or ""), active[1]):
            raise CsrfError(CSRF_DETAIL)
        return user

    async def logout(self, session_token: str) -> None:
        """Revoke the session, so its cookie stops working immediately."""
        user_id = await self._sessions.revoke(hash_api_key(session_token), self._now())
        logger.info("signed out user=%s", user_id)

    async def reset_password(self, email: str, password: str) -> None:
        """Set a new password, sign the user out everywhere and lift any sign-in lock on the
        email (the CLI recovery command).

        Raises:
            InvalidRequestError: The password is too short.
            NotFoundError: No user has this email.
        """
        check_password_strength(password)
        email = normalize_email(email)
        user_id = await self._users.set_password(email, await hash_password_in_thread(password))
        if user_id is None:
            raise NotFoundError(UNKNOWN_USER_DETAIL)
        await self._users.clear_login_failures(hash_api_key(email))
        revoked = await self._sessions.revoke_for_user(user_id, self._now())
        logger.info("password reset user=%s sessions_revoked=%d", user_id, revoked)

    async def _start_session(self, user: UserRecord) -> SignedIn:
        """Store a new session for `user` and return its raw tokens for the cookies."""
        session_token = secrets.token_urlsafe(SESSION_TOKEN_BYTES)
        csrf_token = secrets.token_urlsafe(SESSION_TOKEN_BYTES)
        await self._sessions.insert(user.id, hash_api_key(session_token), hash_api_key(csrf_token))
        return SignedIn(user=user, session_token=session_token, csrf_token=csrf_token)
