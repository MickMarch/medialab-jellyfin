"""The app mounts under the shared API prefix, reads the shared key header, and
its error codes are a superset of the shared set."""

from medialab_contracts import API_KEY_HEADER, API_PREFIX, HEALTH_PATH, CommonErrorCode, MediaType

from medialab_jellyfin.core.errors import ErrorCode
from medialab_jellyfin.main import app
from medialab_jellyfin.schemas.library import AddPathRequest


def test_every_route_is_under_the_shared_prefix() -> None:
    api_paths = list(app.openapi()["paths"])
    assert api_paths
    assert all(p.startswith(API_PREFIX) for p in api_paths)
    assert HEALTH_PATH in api_paths


def test_openapi_security_scheme_uses_the_shared_header() -> None:
    schemes = app.openapi()["components"]["securitySchemes"]
    assert any(s.get("name") == API_KEY_HEADER for s in schemes.values())


def test_error_codes_are_a_superset_of_the_shared_codes() -> None:
    assert {c.value for c in CommonErrorCode} <= {c.value for c in ErrorCode}


def test_add_path_request_uses_the_shared_media_type() -> None:
    request = AddPathRequest(media_type="show", path="/data/tvshows/Bar")
    assert request.media_type is MediaType.SHOW
