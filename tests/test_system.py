"""Tests for the system router: health check endpoint."""

from unittest.mock import patch


class TestHealthCheck:
    def test_returns_online_status_and_uptime(self, unauthed_client):
        with patch("medialab_jellyfin.routers.system.is_reachable", return_value=True):
            response = unauthed_client.get("/api/v1/health")

        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "online"
        assert body["uptime_seconds"] >= 0
        assert body["jellyfin_reachable"] is True

    def test_does_not_require_api_key(self, unauthed_client):
        with patch("medialab_jellyfin.routers.system.is_reachable", return_value=False):
            response = unauthed_client.get("/api/v1/health")

        assert response.status_code == 200

    def test_includes_request_id_header(self, unauthed_client):
        with patch("medialab_jellyfin.routers.system.is_reachable", return_value=False):
            response = unauthed_client.get("/api/v1/health")

        assert "X-Request-ID" in response.headers
