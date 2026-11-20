"""The Discover libraries are gone (MickMarch/medialab#168): no route answers
under /discover and the app needs no Discover setting to start."""

import pytest
from fastapi.testclient import TestClient

from medialab_jellyfin.core.config import AppConfig
from medialab_jellyfin.main import app

FORMER_DISCOVER_ROUTES = [
    ("PUT", "/api/v1/discover/placeholders/movie/603"),
    ("DELETE", "/api/v1/discover/placeholders/movie/603"),
    ("GET", "/api/v1/discover/placeholders?media_type=movie"),
    ("POST", "/api/v1/discover/refresh?media_type=movie"),
    ("GET", "/api/v1/discover/favorites?user_id=u1"),
]


@pytest.mark.parametrize(("method", "url"), FORMER_DISCOVER_ROUTES)
def test_former_discover_route_is_not_found(client, method, url):
    response = client.request(method, url, json={"title": "The Matrix"})

    assert response.status_code == 404


def test_openapi_lists_no_discover_path(client):
    paths = client.get("/openapi.json").json()["paths"]

    assert not [path for path in paths if "/discover" in path]


async def _idle_probe_loop(stop):
    await stop.wait()


def test_app_starts_without_discover_mount_path(monkeypatch, mocker):
    monkeypatch.delenv("DISCOVER_MOUNT_PATH", raising=False)
    mocker.patch("medialab_jellyfin.main.run_probe_loop", _idle_probe_loop)
    mocker.patch("medialab_jellyfin.routers.system.is_reachable", return_value=True)

    with TestClient(app) as started:
        assert started.get("/api/v1/health").status_code == 200

    assert "discover_mount_path" not in AppConfig.model_fields
