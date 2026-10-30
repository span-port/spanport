"""Response model for the health check."""

from pydantic import BaseModel


class HealthResponse(BaseModel):
    """Liveness status of the server process."""

    status: str
