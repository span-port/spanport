"""Liveness endpoint used by Docker and Kubernetes health checks."""

from fastapi import APIRouter

from spanport_server.core.constants import HEALTH_PATH, HEALTH_STATUS_OK
from spanport_server.schemas.health import HealthResponse

router = APIRouter()


@router.get(HEALTH_PATH)
async def get_health() -> HealthResponse:
    """Report that the server process is up and serving requests.

    Checks no dependencies, so a database outage never restarts the server.
    Uvicorn's access log records each call.

    Returns:
        A `HealthResponse` with status "ok".
    """
    return HealthResponse(status=HEALTH_STATUS_OK)
