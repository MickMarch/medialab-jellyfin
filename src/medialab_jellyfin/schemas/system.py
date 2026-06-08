"""Response schemas for system endpoints."""

from pydantic import BaseModel


class HealthResponse(BaseModel):
    """Schema for the application health check response."""

    status: str
    uptime_seconds: float
    jellyfin_reachable: bool
