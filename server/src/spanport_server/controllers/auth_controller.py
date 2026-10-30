"""Sign-in endpoints for the web UI: first-time setup, sign in, sign out and who am I.

A session is a random id in an HttpOnly cookie; a second cookie, readable by the UI, holds the
CSRF token the UI sends back in a header on every request that changes something.
"""

from http import HTTPStatus
from typing import Annotated

from fastapi import APIRouter, Depends, Header, Request, Response

from spanport_server.core.constants import (
    ACCEPT_INVITE_PATH,
    AUTH_LOGIN_PATH,
    AUTH_LOGOUT_PATH,
    AUTH_ME_PATH,
    AUTH_SETUP_PATH,
    COOKIE_PATH,
    CSRF_COOKIE,
    CSRF_COOKIE_SAME_SITE,
    INSPECT_INVITE_PATH,
    MAX_AUTH_BODY_BYTES,
    SESSION_COOKIE,
    SESSION_COOKIE_SAME_SITE,
)
from spanport_server.core.request_body import parse_json_body
from spanport_server.dependencies import get_auth_service, require_user
from spanport_server.schemas.auth import (
    CurrentUserResponse,
    LoginRequest,
    SetupRequest,
    SignedIn,
    UserRecord,
)
from spanport_server.schemas.team import AcceptInviteRequest, InviteDetails, InviteTokenRequest
from spanport_server.services.auth_service import AuthService

router = APIRouter()


def user_response(user: UserRecord) -> CurrentUserResponse:
    """What the UI may know about the signed-in person."""
    return CurrentUserResponse(
        id=user.id, name=user.name, email=user.email, role=user.role, organization=user.org_slug
    )


def set_session_cookies(response: Response, signed_in: SignedIn) -> None:
    """Send the session cookie (HttpOnly) and the CSRF cookie (readable by the UI).

    Both last until the browser closes; the server ends idle sessions on its own.
    """
    response.set_cookie(
        SESSION_COOKIE,
        signed_in.session_token,
        httponly=True,
        secure=True,
        samesite=SESSION_COOKIE_SAME_SITE,
        path=COOKIE_PATH,
    )
    response.set_cookie(
        CSRF_COOKIE,
        signed_in.csrf_token,
        httponly=False,
        secure=True,
        samesite=CSRF_COOKIE_SAME_SITE,
        path=COOKIE_PATH,
    )


@router.post(AUTH_SETUP_PATH, status_code=HTTPStatus.CREATED)
async def complete_setup(
    request: Request,
    response: Response,
    auth_service: Annotated[AuthService, Depends(get_auth_service)],
    content_type: Annotated[str, Header()] = "",
) -> CurrentUserResponse:
    """Create the owner with the one-time setup token and sign them in.

    Returns:
        The new owner (201), with the session and CSRF cookies set.

    Raises:
        InvalidRequestError: Bad field, weak password or unusable organization name (400).
        SetupLinkError: Setup is done, or the link is wrong, used or expired (410).
    """
    body = await parse_json_body(request, content_type, SetupRequest, MAX_AUTH_BODY_BYTES)
    signed_in = await auth_service.complete_setup(body)
    set_session_cookies(response, signed_in)
    return user_response(signed_in.user)


@router.post(AUTH_LOGIN_PATH)
async def login(
    request: Request,
    response: Response,
    auth_service: Annotated[AuthService, Depends(get_auth_service)],
    content_type: Annotated[str, Header()] = "",
) -> CurrentUserResponse:
    """Sign in with email and password.

    Returns:
        The signed-in person, with the session and CSRF cookies set.

    Raises:
        InvalidLoginError: Wrong email or password (401).
    """
    body = await parse_json_body(request, content_type, LoginRequest, MAX_AUTH_BODY_BYTES)
    signed_in = await auth_service.login(body)
    set_session_cookies(response, signed_in)
    return user_response(signed_in.user)


@router.post(INSPECT_INVITE_PATH)
async def inspect_invite(
    request: Request,
    auth_service: Annotated[AuthService, Depends(get_auth_service)],
    content_type: Annotated[str, Header()] = "",
) -> InviteDetails:
    """Who an invite link is for (email, role, organization), shown before accepting it.

    Raises:
        InvalidRequestError: Bad body (400). InviteLinkError: wrong, used or expired (410).
    """
    body = await parse_json_body(request, content_type, InviteTokenRequest, MAX_AUTH_BODY_BYTES)
    return await auth_service.inspect_invite(body.token)


@router.post(ACCEPT_INVITE_PATH, status_code=HTTPStatus.CREATED)
async def accept_invite(
    request: Request,
    response: Response,
    auth_service: Annotated[AuthService, Depends(get_auth_service)],
    content_type: Annotated[str, Header()] = "",
) -> CurrentUserResponse:
    """Accept an invite: create the account and sign in.

    Returns:
        The new user (201), with the session and CSRF cookies set.

    Raises:
        InvalidRequestError: Bad field or weak password (400).
        InviteLinkError: The link is wrong, used, cancelled or expired (410).
    """
    body = await parse_json_body(request, content_type, AcceptInviteRequest, MAX_AUTH_BODY_BYTES)
    signed_in = await auth_service.accept_invite(body)
    set_session_cookies(response, signed_in)
    return user_response(signed_in.user)


@router.post(
    AUTH_LOGOUT_PATH, status_code=HTTPStatus.NO_CONTENT, dependencies=[Depends(require_user)]
)
async def logout(
    request: Request,
    response: Response,
    auth_service: Annotated[AuthService, Depends(get_auth_service)],
) -> None:
    """Revoke this session and clear the cookies.

    Raises:
        NotSignedInError: No valid session (401).
        CsrfError: No CSRF header (403).
    """
    await auth_service.logout(request.cookies.get(SESSION_COOKIE, ""))
    response.delete_cookie(SESSION_COOKIE, path=COOKIE_PATH, secure=True, httponly=True)
    response.delete_cookie(CSRF_COOKIE, path=COOKIE_PATH, secure=True)


@router.get(AUTH_ME_PATH)
async def current_user(user: Annotated[UserRecord, Depends(require_user)]) -> CurrentUserResponse:
    """The signed-in person; the UI calls this to know whether to show Sign in.

    Raises:
        NotSignedInError: No valid session (401).
    """
    return user_response(user)
