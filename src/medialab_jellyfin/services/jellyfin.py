"""Jellyfin API client: connection setup, reachability checks, and library operations."""

import requests

from medialab_jellyfin.core.config import config
from medialab_jellyfin.core.errors import AppException, ErrorCode
from medialab_jellyfin.core.logger import app_logger
from medialab_jellyfin.schemas.library import (
    JellyfinItemsResult,
    JellyfinVirtualFolder,
)

JELLYFIN_REQUEST_TIMEOUT_SECONDS = 5

_PATH_SYSTEM_INFO = "/System/Info/Public"
_PATH_VIRTUAL_FOLDERS = "/Library/VirtualFolders"
_PATH_VIRTUAL_FOLDER_PATHS = "/Library/VirtualFolders/Paths"
_PATH_MEDIA_UPDATED = "/Library/Media/Updated"
_PATH_ITEMS = "/Items"

_COLLECTION_TYPE_MAP: dict[str, str] = {
    "movie": "movies",
    "show": "tvshows",
}


def _base_url() -> str:
    return f"http://{config.jellyfin_host}:{config.jellyfin_port}"


def _auth_headers() -> dict[str, str]:
    return {"Authorization": f"MediaBrowser Token={config.jellyfin_api_key}"}


def _raise_if_unavailable(response: requests.Response) -> None:
    if not response.ok:
        raise AppException(
            status_code=503,
            code=ErrorCode.JELLYFIN_UNAVAILABLE,
            detail=f"Jellyfin returned {response.status_code}.",
        )


def is_reachable() -> bool:
    """Return True if the Jellyfin server responds to a system info request."""
    try:
        response = requests.get(
            f"{_base_url()}{_PATH_SYSTEM_INFO}",
            timeout=JELLYFIN_REQUEST_TIMEOUT_SECONDS,
        )
        return response.ok
    except requests.RequestException:
        app_logger.warning("Jellyfin server unreachable at %s", _base_url())
        return False


def resolve_library_name(media_type: str) -> str:
    """Return the Jellyfin library name for a given media_type via dynamic discovery.

    Raises LIBRARY_NOT_FOUND if no library matches, LIBRARY_AMBIGUOUS if multiple match.
    """
    collection_type = _COLLECTION_TYPE_MAP[media_type]
    response = requests.get(
        f"{_base_url()}{_PATH_VIRTUAL_FOLDERS}",
        headers=_auth_headers(),
        timeout=JELLYFIN_REQUEST_TIMEOUT_SECONDS,
    )
    _raise_if_unavailable(response)

    folders = [JellyfinVirtualFolder.model_validate(f) for f in response.json()]
    matches = [f for f in folders if f.collection_type == collection_type]

    if len(matches) == 0:
        raise AppException(
            status_code=404,
            code=ErrorCode.LIBRARY_NOT_FOUND,
            detail=f"No Jellyfin library found with CollectionType '{collection_type}'.",
        )
    if len(matches) > 1:
        names = ", ".join(f.name for f in matches)
        raise AppException(
            status_code=409,
            code=ErrorCode.LIBRARY_AMBIGUOUS,
            detail=(
                f"Multiple libraries match CollectionType '{collection_type}': {names}. "
                "Provide 'library_name' to select one explicitly."
            ),
        )

    return matches[0].name


def scan_library(path: str, update_type: str) -> None:
    """Notify Jellyfin that media at the given path has been created, modified, or deleted."""
    response = requests.post(
        f"{_base_url()}{_PATH_MEDIA_UPDATED}",
        headers=_auth_headers(),
        json={"Updates": [{"Path": path, "UpdateType": update_type}]},
        timeout=JELLYFIN_REQUEST_TIMEOUT_SECONDS,
    )
    _raise_if_unavailable(response)


def add_library_path(library_name: str, path: str, refresh_library: bool) -> None:
    """Add a local path to an existing Jellyfin library."""
    response = requests.post(
        f"{_base_url()}{_PATH_VIRTUAL_FOLDER_PATHS}",
        headers=_auth_headers(),
        json={"Name": library_name, "Path": path},
        params={"refreshLibrary": refresh_library},
        timeout=JELLYFIN_REQUEST_TIMEOUT_SECONDS,
    )
    _raise_if_unavailable(response)


def search_items(
    search_term: str | None,
    include_item_types: str | None,
    recursive: bool,
    parent_id: str | None,
    limit: int | None,
) -> JellyfinItemsResult:
    """Search Jellyfin library items and return a typed result."""
    params: dict[str, str | bool | int] = {"recursive": recursive}
    if search_term is not None:
        params["searchTerm"] = search_term
    if include_item_types is not None:
        params["includeItemTypes"] = include_item_types
    if parent_id is not None:
        params["parentId"] = parent_id
    if limit is not None:
        params["limit"] = limit

    response = requests.get(
        f"{_base_url()}{_PATH_ITEMS}",
        headers=_auth_headers(),
        params=params,
        timeout=JELLYFIN_REQUEST_TIMEOUT_SECONDS,
    )
    _raise_if_unavailable(response)
    return JellyfinItemsResult.model_validate(response.json())
