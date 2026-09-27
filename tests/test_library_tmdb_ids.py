"""Tests for listing the TMDB ids present in the Jellyfin library."""

from unittest.mock import MagicMock, patch

import pytest
from medialab_contracts import LibraryTmdbIdsResponse, MediaType

from medialab_jellyfin.core.errors import AppException, ErrorCode
from medialab_jellyfin.services import jellyfin

TMDB_IDS_URL = "/api/v1/library/tmdb-ids"
REQUESTS_GET = "medialab_jellyfin.services.jellyfin.requests.get"
SERVICE_FN = "medialab_jellyfin.routers.library.jellyfin.list_library_tmdb_ids"


def _jellyfin_items(items):
    mock = MagicMock()
    mock.status_code = 200
    mock.ok = True
    mock.json.return_value = {"Items": items, "TotalRecordCount": len(items)}
    return mock


def _jellyfin_503():
    mock = MagicMock()
    mock.status_code = 503
    mock.ok = False
    return mock


def _item(item_id, provider_ids):
    return {"Id": item_id, "Name": f"Item {item_id}", "Type": "Movie", "ProviderIds": provider_ids}


class TestListLibraryTmdbIds:
    def test_returns_only_items_with_a_tmdb_provider_id(self):
        items = [
            _item("a", {"Tmdb": "603", "Imdb": "tt0133093"}),
            _item("b", {"Imdb": "tt0000001"}),
            _item("c", {}),
            {"Id": "d", "Name": "No providers"},
            _item("e", {"Tmdb": "27205"}),
        ]
        with patch(REQUESTS_GET, return_value=_jellyfin_items(items)):
            result = jellyfin.list_library_tmdb_ids(MediaType.MOVIE)

        assert result == [603, 27205]

    def test_skips_non_numeric_and_empty_tmdb_ids(self):
        items = [
            _item("a", {"Tmdb": "abc"}),
            _item("b", {"Tmdb": ""}),
            _item("c", {"Tmdb": None}),
            _item("d", {"Tmdb": "1396"}),
        ]
        with patch(REQUESTS_GET, return_value=_jellyfin_items(items)):
            result = jellyfin.list_library_tmdb_ids(MediaType.SHOW)

        assert result == [1396]

    def test_removes_duplicates(self):
        items = [
            _item("a", {"Tmdb": "603"}),
            _item("b", {"Tmdb": "603"}),
            _item("c", {"Tmdb": "604"}),
        ]
        with patch(REQUESTS_GET, return_value=_jellyfin_items(items)):
            result = jellyfin.list_library_tmdb_ids(MediaType.MOVIE)

        assert result == [603, 604]

    @pytest.mark.parametrize(
        ("media_type", "item_type"),
        [(MediaType.MOVIE, "Movie"), (MediaType.SHOW, "Series")],
    )
    def test_filters_by_media_type(self, media_type, item_type):
        with patch(REQUESTS_GET, return_value=_jellyfin_items([])) as mock_get:
            jellyfin.list_library_tmdb_ids(media_type)

        args, kwargs = mock_get.call_args
        assert args[0].endswith("/Items")
        assert kwargs["params"]["IncludeItemTypes"] == item_type
        assert kwargs["params"]["Recursive"] == "true"
        assert kwargs["params"]["Fields"] == "ProviderIds"

    def test_raises_jellyfin_unavailable_on_error_response(self):
        with (
            patch(REQUESTS_GET, return_value=_jellyfin_503()),
            pytest.raises(AppException) as exc_info,
        ):
            jellyfin.list_library_tmdb_ids(MediaType.MOVIE)

        assert exc_info.value.code == ErrorCode.JELLYFIN_UNAVAILABLE


class TestLibraryTmdbIdsRoute:
    def test_returns_the_contract_shape(self, client):
        with patch(SERVICE_FN, return_value=[603, 27205]) as mock_service:
            response = client.get(TMDB_IDS_URL, params={"media_type": "movie"})

        assert response.status_code == 200
        body = LibraryTmdbIdsResponse.model_validate(response.json())
        assert body.media_type is MediaType.MOVIE
        assert body.tmdb_ids == [603, 27205]
        mock_service.assert_called_once_with(MediaType.MOVIE)

    def test_passes_show_media_type(self, client):
        with patch(SERVICE_FN, return_value=[]) as mock_service:
            response = client.get(TMDB_IDS_URL, params={"media_type": "show"})

        assert response.status_code == 200
        assert response.json() == {"media_type": "show", "tmdb_ids": []}
        mock_service.assert_called_once_with(MediaType.SHOW)

    def test_requires_media_type(self, client):
        response = client.get(TMDB_IDS_URL)

        assert response.status_code == 422

    def test_rejects_unknown_media_type(self, client):
        response = client.get(TMDB_IDS_URL, params={"media_type": "music"})

        assert response.status_code == 422

    def test_requires_api_key(self, unauthed_client):
        response = unauthed_client.get(TMDB_IDS_URL, params={"media_type": "movie"})

        assert response.status_code == 403

    def test_returns_503_when_jellyfin_unavailable(self, client):
        with patch(REQUESTS_GET, return_value=_jellyfin_503()):
            response = client.get(TMDB_IDS_URL, params={"media_type": "movie"})

        assert response.status_code == 503
        assert response.json()["code"] == "JELLYFIN_UNAVAILABLE"

    def test_includes_request_id_header(self, client):
        with patch(SERVICE_FN, return_value=[]):
            response = client.get(TMDB_IDS_URL, params={"media_type": "movie"})

        assert "X-Request-ID" in response.headers
