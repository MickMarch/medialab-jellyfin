"""Discover router: placeholder folders, Discover library refresh, and per-user favorites."""

from pathlib import Path

from fastapi import APIRouter, Query, Request
from fastapi import status as fastapi_status
from medialab_contracts import (
    FavoriteScope,
    JellyfinRequestEvent,
    MediaType,
    PlaceholdersResponse,
    PlaceholderWrite,
)

from medialab_jellyfin.core.config import config
from medialab_jellyfin.core.constants import TAG_DISCOVER
from medialab_jellyfin.core.errors import AppException, ErrorCode
from medialab_jellyfin.core.limiter import RATE_LIMIT_DEFAULT, limiter
from medialab_jellyfin.schemas.errors import ErrorResponse
from medialab_jellyfin.services import jellyfin, placeholders

router = APIRouter(prefix="/discover", tags=[TAG_DISCOVER])

_PLACEHOLDER_PATH = "/placeholders/{media_type}/{tmdb_id}"

_ERROR_RESPONSES = {
    403: {"model": ErrorResponse},
    429: {"model": ErrorResponse},
    503: {"model": ErrorResponse},
}
_LIBRARY_NOT_FOUND_RESPONSE = {
    404: {"model": ErrorResponse, "description": "A Discover library is missing in Jellyfin."}
}


def _root() -> Path:
    if not config.discover_mount_path:
        raise AppException(
            status_code=fastapi_status.HTTP_503_SERVICE_UNAVAILABLE,
            code=ErrorCode.DISCOVER_NOT_CONFIGURED,
            detail="DISCOVER_MOUNT_PATH is not set.",
        )
    return Path(config.discover_mount_path)


def _refresh(media_type: MediaType) -> None:
    jellyfin.refresh_item(jellyfin.discover_library_ids()[media_type])


@router.put(
    _PLACEHOLDER_PATH,
    status_code=fastapi_status.HTTP_204_NO_CONTENT,
    summary="Create a placeholder, or update its title, year or state.",
    responses={**_ERROR_RESPONSES, **_LIBRARY_NOT_FOUND_RESPONSE},
)
@limiter.limit(RATE_LIMIT_DEFAULT)
def put_placeholder(
    request: Request,
    media_type: MediaType,
    tmdb_id: int,
    body: PlaceholderWrite,
    refresh: bool = Query(default=True),
) -> None:
    changed = placeholders.write_placeholder(
        _root(),
        media_type=media_type,
        tmdb_id=tmdb_id,
        title=body.title,
        year=body.year,
        state=body.state,
    )
    if changed and refresh:
        _refresh(media_type)


@router.delete(
    _PLACEHOLDER_PATH,
    status_code=fastapi_status.HTTP_204_NO_CONTENT,
    summary="Remove a placeholder; absent is not an error.",
    responses={**_ERROR_RESPONSES, **_LIBRARY_NOT_FOUND_RESPONSE},
)
@limiter.limit(RATE_LIMIT_DEFAULT)
def delete_placeholder(
    request: Request,
    media_type: MediaType,
    tmdb_id: int,
    refresh: bool = Query(default=True),
) -> None:
    removed = placeholders.remove_placeholder(_root(), media_type, tmdb_id)
    if removed and refresh:
        _refresh(media_type)


@router.get(
    "/placeholders",
    response_model=PlaceholdersResponse,
    status_code=fastapi_status.HTTP_200_OK,
    summary="List the placeholders of one media type.",
    responses={**_ERROR_RESPONSES},
)
@limiter.limit(RATE_LIMIT_DEFAULT)
def list_placeholders(request: Request, media_type: MediaType) -> PlaceholdersResponse:
    return PlaceholdersResponse(
        media_type=media_type,
        placeholders=placeholders.list_placeholders(_root(), media_type),
    )


@router.post(
    "/refresh",
    status_code=fastapi_status.HTTP_204_NO_CONTENT,
    summary="Rescan one Discover library, after a batch of refresh=false writes.",
    responses={**_ERROR_RESPONSES, **_LIBRARY_NOT_FOUND_RESPONSE},
)
@limiter.limit(RATE_LIMIT_DEFAULT)
def refresh_library(request: Request, media_type: MediaType) -> None:
    _refresh(media_type)


@router.get(
    "/favorites",
    response_model=list[JellyfinRequestEvent],
    status_code=fastapi_status.HTTP_200_OK,
    summary="One user's favorites on Discover placeholders or on real library items.",
    responses={**_ERROR_RESPONSES, **_LIBRARY_NOT_FOUND_RESPONSE},
)
@limiter.limit(RATE_LIMIT_DEFAULT)
def list_favorites(
    request: Request,
    user_id: str,
    scope: FavoriteScope = FavoriteScope.DISCOVER,
) -> list[JellyfinRequestEvent]:
    return jellyfin.list_favorites(user_id, scope)
