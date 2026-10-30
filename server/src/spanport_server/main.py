"""FastAPI application for the Spanport server."""

import asyncio
import contextlib
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from spanport_server.controllers import (
    alert_controller,
    api_key_controller,
    auth_controller,
    health_controller,
    log_export_controller,
    log_search_controller,
    log_tail_controller,
    otlp_logs_controller,
    otlp_traces_controller,
    project_controller,
    team_controller,
    trace_controller,
)
from spanport_server.core.config import Settings, load_settings
from spanport_server.core.constants import SERVICE_NAME
from spanport_server.core.error_handlers import install_error_handlers
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
    postgres_engine = create_postgres_engine(settings)
    app.state.postgres_sessionmaker = async_sessionmaker(postgres_engine, expire_on_commit=False)
    app.state.clickhouse_client = await create_clickhouse_client(settings)
    await announce_setup_token(app.state.postgres_sessionmaker)
    alert_checks = asyncio.create_task(
        run_alert_checks(
            build_alert_check_service(
                app.state.postgres_sessionmaker, app.state.clickhouse_client, settings
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
    """Build the FastAPI app with every router and error handler registered.

    Returns:
        The configured FastAPI application.
    """
    app = FastAPI(title=SERVICE_NAME, lifespan=lifespan)
    install_error_handlers(app)
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
    return app


app = create_app()
