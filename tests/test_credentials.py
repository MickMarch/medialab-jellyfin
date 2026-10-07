"""Credential health: tracker, classification on Jellyfin calls, probe loop, health field."""

import asyncio

import pytest
import requests
from medialab_contracts import CREDENTIAL_JELLYFIN_API_KEY, CredentialStatus

from medialab_jellyfin.core.credentials import CredentialTracker, credentials
from medialab_jellyfin.core.errors import AppException
from medialab_jellyfin.services import credential_probe, jellyfin

HTTP_OK = 200
HTTP_UNAUTHORIZED = 401
HTTP_SERVER_ERROR = 500


@pytest.fixture(autouse=True)
def fresh_tracker():
    credentials.reset()
    yield
    credentials.reset()


class _Response:
    def __init__(self, status_code: int) -> None:
        self.status_code = status_code
        self.ok = status_code == HTTP_OK

    def json(self) -> dict:
        return {}


class TestTracker:
    def test_starts_unknown(self) -> None:
        tracker = CredentialTracker()
        state = tracker.snapshot()[CREDENTIAL_JELLYFIN_API_KEY]
        assert state.status is CredentialStatus.UNKNOWN

    def test_marks_record_detail(self) -> None:
        tracker = CredentialTracker()
        tracker.mark_invalid(CREDENTIAL_JELLYFIN_API_KEY, "HTTP 401")
        assert tracker.snapshot()[CREDENTIAL_JELLYFIN_API_KEY].detail == "HTTP 401"


class TestClassification:
    def test_unauthorized_marks_invalid_and_raises(self) -> None:
        with pytest.raises(AppException):
            jellyfin._raise_if_unavailable(_Response(HTTP_UNAUTHORIZED))
        state = credentials.snapshot()[CREDENTIAL_JELLYFIN_API_KEY]
        assert state.status is CredentialStatus.INVALID
        assert str(HTTP_UNAUTHORIZED) in state.detail

    def test_other_errors_do_not_touch_the_credential(self) -> None:
        with pytest.raises(AppException):
            jellyfin._raise_if_unavailable(_Response(HTTP_SERVER_ERROR))
        assert (
            credentials.snapshot()[CREDENTIAL_JELLYFIN_API_KEY].status is CredentialStatus.UNKNOWN
        )

    def test_success_marks_ok(self) -> None:
        jellyfin._raise_if_unavailable(_Response(HTTP_OK))
        assert credentials.snapshot()[CREDENTIAL_JELLYFIN_API_KEY].status is CredentialStatus.OK


class TestProbe:
    def test_probe_calls_system_info_with_the_key(self, mocker) -> None:
        mocker.patch.object(jellyfin.config, "jellyfin_api_key", "k")
        get = mocker.patch.object(requests, "get", return_value=_Response(HTTP_OK))
        jellyfin.probe_api_key()
        assert get.call_args.args[0].endswith(jellyfin._PATH_SYSTEM_INFO_AUTHENTICATED)
        assert "k" in get.call_args.kwargs["headers"]["Authorization"]
        assert credentials.snapshot()[CREDENTIAL_JELLYFIN_API_KEY].status is CredentialStatus.OK

    def test_probe_refusal_marks_invalid(self, mocker) -> None:
        mocker.patch.object(jellyfin.config, "jellyfin_api_key", "k")
        mocker.patch.object(requests, "get", return_value=_Response(HTTP_UNAUTHORIZED))
        jellyfin.probe_api_key()
        assert (
            credentials.snapshot()[CREDENTIAL_JELLYFIN_API_KEY].status is CredentialStatus.INVALID
        )

    def test_probe_transport_failure_marks_unreachable(self, mocker) -> None:
        mocker.patch.object(jellyfin.config, "jellyfin_api_key", "k")
        mocker.patch.object(requests, "get", side_effect=requests.ConnectionError("down"))
        jellyfin.probe_api_key()
        assert (
            credentials.snapshot()[CREDENTIAL_JELLYFIN_API_KEY].status
            is CredentialStatus.UNREACHABLE
        )

    def test_probe_without_a_key_marks_invalid_without_a_call(self, mocker) -> None:
        mocker.patch.object(jellyfin.config, "jellyfin_api_key", None)
        get = mocker.patch.object(requests, "get")
        jellyfin.probe_api_key()
        get.assert_not_called()
        assert (
            credentials.snapshot()[CREDENTIAL_JELLYFIN_API_KEY].status is CredentialStatus.INVALID
        )

    def test_loop_probes_after_delay_then_on_interval(self, mocker) -> None:
        probe = mocker.patch.object(credential_probe, "probe_api_key")
        mocker.patch.object(credential_probe.config, "credential_check_interval_seconds", 42)
        waits: list[float] = []
        stop = asyncio.Event()

        async def fake_sleep(seconds: float) -> None:
            waits.append(seconds)
            if len(waits) >= 3:
                stop.set()

        asyncio.run(credential_probe.run_probe_loop(stop, sleep=fake_sleep, startup_delay=5.0))
        assert waits == [5.0, 42.0, 42.0]
        assert probe.call_count == 2


class TestHealthField:
    def test_health_reports_credentials(self, unauthed_client, mocker) -> None:
        mocker.patch("medialab_jellyfin.routers.system.is_reachable", return_value=True)
        credentials.mark_ok(CREDENTIAL_JELLYFIN_API_KEY)
        body = unauthed_client.get("/api/v1/health").json()
        assert body["credentials"][CREDENTIAL_JELLYFIN_API_KEY]["status"] == "ok"
