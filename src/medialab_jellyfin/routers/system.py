"""System router: health check and operational status endpoints."""

import time

from fastapi import APIRouter
from fastapi import status as fastapi_status

from medialab_jellyfin.core.constants import API_START_TIME, TAG_SYSTEM
from medialab_jellyfin.core.limiter import limiter
from medialab_jellyfin.schemas.system import HealthResponse
from medialab_jellyfin.services.jellyfin import is_reachable

router = APIRouter(tags=[TAG_SYSTEM])


@router.get(
    "/health",
    response_model=HealthResponse,
    status_code=fastapi_status.HTTP_200_OK,
    summary="Returns the current operational status and uptime of the API.",
)
@limiter.exempt
def api_health_check() -> HealthResponse:
    """Return current uptime and Jellyfin reachability status for liveness monitoring."""
    uptime_seconds: float = time.time() - API_START_TIME

    return HealthResponse(
        status="online",
        uptime_seconds=round(uptime_seconds, 2),
        jellyfin_reachable=is_reachable(),
    )
