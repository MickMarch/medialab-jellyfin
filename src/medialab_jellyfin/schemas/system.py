"""Response schemas for system endpoints."""

from medialab_contracts import CredentialState
from pydantic import BaseModel


class HealthResponse(BaseModel):
    """Schema for the application health check response."""

    status: str
    uptime_seconds: float
    jellyfin_reachable: bool
    credentials: dict[str, CredentialState] = {}
    """Per-credential health for the key this service owns."""
