"""Wires repositories into services for each request (FastAPI Depends)."""

from collections.abc import Awaitable, Callable
from typing import Annotated

from clickhouse_connect.driver.asyncclient import AsyncClient
from fastapi import Depends, Header, Request
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from spanport_server.clients.email_client import EmailClient
from spanport_server.core.config import Settings
from spanport_server.core.constants import (
    BEARER_PREFIX,
    CSRF_HEADER,
    MANAGER_ROLES,
    NOT_A_MANAGER_DETAIL,
    NOT_A_RESPONDER_DETAIL,
    RESPONDER_ROLES,
    SAFE_METHODS,
    SESSION_COOKIE,
)
from spanport_server.core.errors import NotAllowedError
from spanport_server.repositories.clickhouse.log_repository import LogRepository
from spanport_server.repositories.clickhouse.log_search_repository import LogSearchRepository
from spanport_server.repositories.clickhouse.project_data_repository import ProjectDataRepository
from spanport_server.repositories.clickhouse.span_repository import SpanRepository
from spanport_server.repositories.clickhouse.span_search_repository import SpanSearchRepository
from spanport_server.repositories.postgres.alert_event_repository import AlertEventRepository
from spanport_server.repositories.postgres.alert_rule_repository import AlertRuleRepository
from spanport_server.repositories.postgres.api_key_repository import ApiKeyRepository
from spanport_server.repositories.postgres.session_repository import SessionRepository
from spanport_server.repositories.postgres.team_repository import TeamRepository
from spanport_server.repositories.postgres.tenant_repository import TenantRepository
from spanport_server.repositories.postgres.user_repository import UserRepository
from spanport_server.schemas.api_key import ApiKeyRecord, KeyType, Scope
from spanport_server.schemas.auth import Caller, UserRecord
from spanport_server.services.alert_check_service import AlertCheckService
from spanport_server.services.alert_event_service import AlertEventService
from spanport_server.services.alert_notifier import AlertNotifier
from spanport_server.services.alert_rule_service import AlertRuleService
from spanport_server.services.api_key_auth_service import ApiKeyAuthService
from spanport_server.services.api_key_service import ApiKeyService
from spanport_server.services.auth_service import AuthService
from spanport_server.services.log_export_service import LogExportService
from spanport_server.services.log_ingest_service import LogIngestService
from spanport_server.services.log_search_service import LogSearchService
from spanport_server.services.log_tail_service import LogTailService
from spanport_server.services.project_service import ProjectService
from spanport_server.services.span_ingest_service import SpanIngestService
from spanport_server.services.team_service import TeamService
from spanport_server.services.trace_service import TraceService


def get_api_key_auth_service(request: Request) -> ApiKeyAuthService:
    """Build the key check service on the app's Postgres pool."""
    return ApiKeyAuthService(ApiKeyRepository(request.app.state.postgres_sessionmaker))


def get_api_key_service(request: Request) -> ApiKeyService:
    """Build the key management service on the app's Postgres pool."""
    sessionmaker = request.app.state.postgres_sessionmaker
    return ApiKeyService(TenantRepository(sessionmaker), ApiKeyRepository(sessionmaker))


def get_auth_service(request: Request) -> AuthService:
    """Build the sign-in and session service on the app's Postgres pool."""
    sessionmaker = request.app.state.postgres_sessionmaker
    return AuthService(UserRepository(sessionmaker), SessionRepository(sessionmaker))


def get_log_ingest_service(request: Request) -> LogIngestService:
    """Build the log ingest service on the app's ClickHouse client."""
    return LogIngestService(LogRepository(request.app.state.clickhouse_client))


def get_span_ingest_service(request: Request) -> SpanIngestService:
    """Build the span (trace) ingest service on the app's ClickHouse client."""
    return SpanIngestService(SpanRepository(request.app.state.clickhouse_client))


def get_trace_service(request: Request) -> TraceService:
    """Build the traces (Requests screen) service on Postgres and ClickHouse."""
    return TraceService(
        TenantRepository(request.app.state.postgres_sessionmaker),
        SpanSearchRepository(request.app.state.clickhouse_client),
    )


def get_log_search_service(request: Request) -> LogSearchService:
    """Build the log search service on the app's Postgres pool and ClickHouse client."""
    return LogSearchService(
        TenantRepository(request.app.state.postgres_sessionmaker),
        LogSearchRepository(request.app.state.clickhouse_client),
    )


def get_log_export_service(request: Request) -> LogExportService:
    """Build the log export service on the app's Postgres pool and ClickHouse client."""
    return LogExportService(
        TenantRepository(request.app.state.postgres_sessionmaker),
        LogSearchRepository(request.app.state.clickhouse_client),
    )


def get_log_tail_service(request: Request) -> LogTailService:
    """Build the live tail service on the app's Postgres pool and ClickHouse client."""
    return LogTailService(
        TenantRepository(request.app.state.postgres_sessionmaker),
        LogSearchRepository(request.app.state.clickhouse_client),
    )


def get_project_service(request: Request) -> ProjectService:
    """Build the projects service on the app's Postgres pool and ClickHouse client."""
    return ProjectService(
        TenantRepository(request.app.state.postgres_sessionmaker),
        ProjectDataRepository(request.app.state.clickhouse_client),
    )


def build_alert_notifier(settings: Settings) -> AlertNotifier:
    """The alert emailer; without SMTP settings it reports that email isn't set up."""
    return AlertNotifier(EmailClient(settings) if settings.smtp_host else None, settings.ui_url)


def build_alert_check_service(
    sessionmaker: async_sessionmaker[AsyncSession], clickhouse: AsyncClient, settings: Settings
) -> AlertCheckService:
    """The service the alert check job runs, built once at start-up."""
    return AlertCheckService(
        AlertRuleRepository(sessionmaker),
        AlertEventRepository(sessionmaker),
        LogSearchRepository(clickhouse),
        TenantRepository(sessionmaker),
        build_alert_notifier(settings),
    )


def get_alert_rule_service(request: Request) -> AlertRuleService:
    """Build the alert rules service on the app's Postgres pool and settings."""
    sessionmaker = request.app.state.postgres_sessionmaker
    return AlertRuleService(
        AlertRuleRepository(sessionmaker),
        TenantRepository(sessionmaker),
        build_alert_notifier(request.app.state.settings),
    )


def get_alert_event_service(request: Request) -> AlertEventService:
    """Build the alerts (events) service on the app's Postgres pool."""
    sessionmaker = request.app.state.postgres_sessionmaker
    return AlertEventService(AlertEventRepository(sessionmaker), TenantRepository(sessionmaker))


def get_team_service(request: Request) -> TeamService:
    """Build the users and invites service on the app's Postgres pool."""
    sessionmaker = request.app.state.postgres_sessionmaker
    return TeamService(TeamRepository(sessionmaker), SessionRepository(sessionmaker))


def bearer_token(authorization: str) -> str | None:
    """The key from an `Authorization: Bearer <key>` header, or None if there isn't one."""
    if not authorization.startswith(BEARER_PREFIX):
        return None
    return authorization.removeprefix(BEARER_PREFIX)


async def require_data_key(
    auth_service: Annotated[ApiKeyAuthService, Depends(get_api_key_auth_service)],
    authorization: Annotated[str, Header()] = "",
) -> ApiKeyRecord:
    """Authenticate the `Authorization: Bearer sp_ingest_...` header before the body is read.

    Returns:
        The data key, with the org and project the request's data belongs to.

    Raises:
        InvalidKeyError: The header is missing or the key is not a valid data key.
    """
    return await auth_service.authenticate(bearer_token(authorization), KeyType.INGEST)


async def require_user(
    request: Request, auth_service: Annotated[AuthService, Depends(get_auth_service)]
) -> UserRecord:
    """The signed-in person, from the session cookie.

    Requests other than GET must also send the CSRF token from the CSRF cookie in a header.

    Raises:
        NotSignedInError: No valid session (401).
        CsrfError: The CSRF header is missing or wrong (403).
    """
    return await auth_service.authenticate(
        request.cookies.get(SESSION_COOKIE),
        request.headers.get(CSRF_HEADER),
        needs_csrf=request.method not in SAFE_METHODS,
    )


async def require_manager(user: Annotated[UserRecord, Depends(require_user)]) -> Caller:
    """A signed-in owner or admin, the only roles that manage projects and keys.

    Raises:
        NotSignedInError / CsrfError: As for require_user.
        NotAllowedError: The person is a member or viewer (403).
    """
    if user.role not in MANAGER_ROLES:
        raise NotAllowedError(NOT_A_MANAGER_DETAIL)
    return user_caller(user)


async def require_signed_in(user: Annotated[UserRecord, Depends(require_user)]) -> Caller:
    """Any signed-in person, whatever their role, as a Caller.

    Raises:
        NotSignedInError / CsrfError: As for require_user.
    """
    return user_caller(user)


async def require_responder(user: Annotated[UserRecord, Depends(require_user)]) -> Caller:
    """A signed-in owner, admin or member: the roles that acknowledge and resolve alerts.

    Raises:
        NotSignedInError / CsrfError: As for require_user.
        NotAllowedError: The person is a viewer (403).
    """
    if user.role not in RESPONDER_ROLES:
        raise NotAllowedError(NOT_A_RESPONDER_DETAIL)
    return user_caller(user)


def user_caller(user: UserRecord) -> Caller:
    """A signed-in person as a Caller, with their id for actions that record who did them."""
    return Caller(
        org_id=user.org_id,
        label=f"user={user.id}",
        user_id=user.id,
        role=user.role,
        project_ids=user.project_ids,
    )


def require_reader(scope: Scope) -> Callable[..., Awaitable[Caller]]:
    """A dependency for data endpoints: an admin key holding `scope`, or else a signed-in person.

    A request with an Authorization header is treated as a script and needs a valid admin key;
    without one, the browser's session cookie is checked. Every role may read.
    Raises InvalidKeyError, MissingScopeError, NotSignedInError or CsrfError.
    """

    async def require(
        request: Request,
        key_service: Annotated[ApiKeyAuthService, Depends(get_api_key_auth_service)],
        auth_service: Annotated[AuthService, Depends(get_auth_service)],
        authorization: Annotated[str, Header()] = "",
    ) -> Caller:
        """Authenticate the admin key or the session for this scope."""
        if authorization:
            key = await key_service.authenticate(
                bearer_token(authorization), KeyType.ADMIN, required_scope=scope
            )
            return Caller(org_id=key.org_id, label=f"key=...{key.last_four}")
        return user_caller(await require_user(request, auth_service))

    return require


require_logs_reader = require_reader(Scope.LOGS_READ)
require_projects_reader = require_reader(Scope.PROJECTS_READ)
