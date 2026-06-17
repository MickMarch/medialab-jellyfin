"""Library router: scan trigger, path management, and item search endpoints."""

from fastapi import APIRouter, Query, Request
from fastapi import status as fastapi_status

from medialab_jellyfin.core.constants import TAG_LIBRARY
from medialab_jellyfin.core.limiter import limiter, RATE_LIMIT_DEFAULT
from medialab_jellyfin.schemas.errors import ErrorResponse
from medialab_jellyfin.schemas.library import (
    AddPathRequest,
    ItemsResponse,
    LibraryItem,
    ScanRequest,
)
from medialab_jellyfin.services import jellyfin

router = APIRouter(tags=[TAG_LIBRARY])

_ERROR_RESPONSES = {
    403: {"model": ErrorResponse},
    429: {"model": ErrorResponse},
    503: {"model": ErrorResponse},
}


@router.post(
    "/library/scan",
    status_code=fastapi_status.HTTP_204_NO_CONTENT,
    summary="Trigger a Jellyfin library scan for a given path.",
    responses={**_ERROR_RESPONSES},
)
@limiter.limit(RATE_LIMIT_DEFAULT)
def scan_library(request: Request, body: ScanRequest) -> None:
    jellyfin.scan_library(path=body.path, update_type=body.update_type.value)


@router.post(
    "/library/paths",
    status_code=fastapi_status.HTTP_204_NO_CONTENT,
    summary="Add a local path to a Jellyfin library.",
    responses={
        **_ERROR_RESPONSES,
        404: {"model": ErrorResponse, "description": "No library found for the given media_type."},
        409: {"model": ErrorResponse, "description": "Multiple libraries match; provide library_name to disambiguate."},
    },
)
@limiter.limit(RATE_LIMIT_DEFAULT)
def add_library_path(request: Request, body: AddPathRequest) -> None:
    library_name = body.library_name or jellyfin.resolve_library_name(body.media_type.value)
    jellyfin.add_library_path(
        library_name=library_name,
        path=body.path,
        refresh_library=body.refresh_library,
    )


@router.get(
    "/library/items",
    response_model=ItemsResponse,
    status_code=fastapi_status.HTTP_200_OK,
    summary="Search Jellyfin library items.",
    responses={**_ERROR_RESPONSES},
)
@limiter.limit(RATE_LIMIT_DEFAULT)
def get_library_items(
    request: Request,
    search_term: str | None = Query(default=None),
    include_item_types: str | None = Query(default=None),
    recursive: bool = Query(default=True),
    parent_id: str | None = Query(default=None),
    limit: int | None = Query(default=None),
) -> ItemsResponse:
    result = jellyfin.search_items(
        search_term=search_term,
        include_item_types=include_item_types,
        recursive=recursive,
        parent_id=parent_id,
        limit=limit,
    )
    return ItemsResponse(
        items=[LibraryItem.from_jellyfin(item) for item in result.items],
        total_record_count=result.total_record_count,
    )
