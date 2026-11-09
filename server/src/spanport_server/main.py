"""FastAPI application for the Spanport server."""

import asyncio
import contextlib
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from spanport_server.controllers import (
    alert_controller,
    api_key_controller,
    auth_controller,
    endpoint_controller,
    error_controller,
    health_controller,
    log_export_controller,
    log_search_controller,
    log_tail_controller,
    otlp_logs_controller,
    otlp_traces_controller,
    project_controller,
    service_map_controller,
    storage_controller,
    team_controller,
    trace_controller,
)
from spanport_server.core.config import ApiDocsSettings, Settings, load_settings
from spanport_server.core.constants import API_DOCS_PATH, API_REDOC_PATH, OPENAPI_PATH, SERVICE_NAME
from spanport_server.core.error_handlers import install_error_handlers
from spanport_server.core.request_limits import (
    api_limits,
    install_rate_limits,
    limit_public_routes,
)
from spanport_server.dependencies import build_alert_check_service
from spanport_server.jobs.alert_check_job import run_alert_checks
from spanport_server.repositories.clickhouse.database import create_clickhouse_client
from spanport_server.repositories.postgres.database import create_postgres_engine
from spanport_server.repositories.postgres.session_repository import SessionRepository
from spanport_server.repositories.postgres.user_repository import UserRepository
from spanport_server.services.auth_service import AuthService

logger = logging.getLogger(__name__)


async def announce_setup_token(sessionmaker: async_sessionmaker[AsyncSession]) -> None:
    """While nobody can sign in yet, log a one-time token that creates the owner (PRD: setup)."""
    auth_service = AuthService(UserRepository(sessionmaker), SessionRepository(sessionmaker))
    token = await auth_service.issue_setup_token()
    if token is not None:
        logger.warning(
            "no users yet: open the UI's Set up page and paste this token to create the owner "
            "(single use, expires in 1 hour) setup_token=%s",
            token,
        )


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Open the Postgres pool and ClickHouse client at start-up; close them at shutdown."""
    settings = load_settings(Settings)
    app.state.settings = settings
    app.state.api_limits = api_limits(settings)
    postgres_engine = create_postgres_engine(settings)
    app.state.postgres_sessionmaker = async_sessionmaker(postgres_engine, expire_on_commit=False)
    app.state.clickhouse_client = await create_clickhouse_client(settings)
    await announce_setup_token(app.state.postgres_sessionmaker)
    alert_checks = asyncio.create_task(
        run_alert_checks(
            build_alert_check_service(
                app.state.postgres_sessionmaker,
                app.state.clickhouse_client,
                settings,
                app.state.rate_limiter,
            )
        )
    )
    if not settings.smtp_host:
        logger.warning("SPANPORT_SMTP_HOST is not set: alert rules can't email anyone")
    yield
    alert_checks.cancel()
    with contextlib.suppress(asyncio.CancelledError):
        await alert_checks
    await app.state.clickhouse_client.close()
    await postgres_engine.dispose()


def create_app() -> FastAPI:
    """Build the FastAPI app with every router, error handler and rate limit registered.

    The API docs are served only with SPANPORT_API_DOCS=true.

    Returns:
        The configured FastAPI application.
    """
    api_docs = load_settings(ApiDocsSettings).api_docs
    app = FastAPI(
        title=SERVICE_NAME,
        lifespan=lifespan,
        docs_url=API_DOCS_PATH if api_docs else None,
        redoc_url=API_REDOC_PATH if api_docs else None,
        openapi_url=OPENAPI_PATH if api_docs else None,
        dependencies=[Depends(limit_public_routes)],
    )
    install_error_handlers(app)
    install_rate_limits(app)
    app.include_router(health_controller.router)
    app.include_router(otlp_logs_controller.router)
    app.include_router(otlp_traces_controller.router)
    app.include_router(api_key_controller.router)
    app.include_router(auth_controller.router)
    app.include_router(log_search_controller.router)
    app.include_router(log_tail_controller.router)
    app.include_router(log_export_controller.router)
    app.include_router(project_controller.router)
    app.include_router(alert_controller.router)
    app.include_router(team_controller.router)
    app.include_router(trace_controller.router)
    app.include_router(endpoint_controller.router)
    app.include_router(error_controller.router)
    app.include_router(service_map_controller.router)
    app.include_router(storage_controller.router)
    return app


app = create_app()
