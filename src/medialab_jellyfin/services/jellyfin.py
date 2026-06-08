"""Jellyfin API client: connection setup and reachability checks."""

import requests

from medialab_jellyfin.core.config import config
from medialab_jellyfin.core.logger import app_logger

JELLYFIN_REQUEST_TIMEOUT_SECONDS = 5


def _base_url() -> str:
    return f"http://{config.jellyfin_host}:{config.jellyfin_port}"


def is_reachable() -> bool:
    """Return True if the Jellyfin server responds to a system info request."""
    try:
        response = requests.get(
            f"{_base_url()}/System/Info/Public",
            timeout=JELLYFIN_REQUEST_TIMEOUT_SECONDS,
        )
        return response.ok
    except requests.RequestException:
        app_logger.warning("Jellyfin server unreachable at %s", _base_url())
        return False
