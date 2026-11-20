"""Tests for listing the episodes of a series present in the Jellyfin library."""

from unittest.mock import MagicMock, patch

import pytest
from medialab_contracts import EpisodeKey, LibraryEpisodesResponse

from medialab_jellyfin.core.errors import AppException, ErrorCode
from medialab_jellyfin.services import jellyfin

EPISODES_URL = "/api/v1/library/episodes"
REQUESTS_GET = "medialab_jellyfin.services.jellyfin.requests.get"
SERVICE_FN = "medialab_jellyfin.routers.library.jellyfin.list_library_episodes"

SERIES_TMDB_ID = 1396
SERIES_ID = "series-1396"


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


def _series(item_id, tmdb_id):
    return {
        "Id": item_id,
        "Name": f"Series {item_id}",
        "Type": "Series",
        "ProviderIds": {"Tmdb": str(tmdb_id)},
    }


def _episode(item_id, season=None, episode=None):
    item = {"Id": item_id, "Name": f"Episode {item_id}", "Type": "Episode"}
    if season is not None:
        item["ParentIndexNumber"] = season
    if episode is not None:
        item["IndexNumber"] = episode
    return item


def _two_step(series_items, episode_items):
    return [_jellyfin_items(series_items), _jellyfin_items(episode_items)]


class TestListLibraryEpisodes:
    def test_unknown_series_returns_empty_without_querying_episodes(self):
        series_items = [_series("other", 603)]
        with patch(REQUESTS_GET, return_value=_jellyfin_items(series_items)) as mock_get:
            result = jellyfin.list_library_episodes(SERIES_TMDB_ID)

        assert result == []
        assert mock_get.call_count == 1

    def test_queries_series_then_episodes_under_the_matched_series(self):
        series_items = [_series("other", 603), _series(SERIES_ID, SERIES_TMDB_ID)]
        episodes = [_episode("e1", 1, 1)]
        with patch(REQUESTS_GET, side_effect=_two_step(series_items, episodes)) as mock_get:
            jellyfin.list_library_episodes(SERIES_TMDB_ID)

        assert mock_get.call_count == 2
        series_args, series_kwargs = mock_get.call_args_list[0]
        assert series_args[0].endswith("/Items")
        assert series_kwargs["params"]["IncludeItemTypes"] == "Series"
        assert series_kwargs["params"]["Recursive"] == "true"
        assert series_kwargs["params"]["Fields"] == "ProviderIds"

        episode_args, episode_kwargs = mock_get.call_args_list[1]
        assert episode_args[0].endswith("/Items")
        assert episode_kwargs["params"]["ParentId"] == SERIES_ID
        assert episode_kwargs["params"]["IncludeItemTypes"] == "Episode"
        assert episode_kwargs["params"]["Recursive"] == "true"
        assert episode_kwargs["params"]["Fields"] == "ParentIndexNumber,IndexNumber"

    def test_returns_season_and_episode_keys(self):
        episodes = [_episode("e1", 1, 1), _episode("e2", 1, 2), _episode("e3", 2, 1)]
        with patch(REQUESTS_GET, side_effect=_two_step([_series(SERIES_ID, 1396)], episodes)):
            result = jellyfin.list_library_episodes(SERIES_TMDB_ID)

        assert result == [
            EpisodeKey(season=1, episode=1),
            EpisodeKey(season=1, episode=2),
            EpisodeKey(season=2, episode=1),
        ]

    def test_skips_items_missing_season_or_episode_number(self):
        episodes = [
            _episode("no-season", episode=3),
            _episode("no-episode", season=2),
            _episode("neither"),
            _episode("ok", 2, 3),
        ]
        with patch(REQUESTS_GET, side_effect=_two_step([_series(SERIES_ID, 1396)], episodes)):
            result = jellyfin.list_library_episodes(SERIES_TMDB_ID)

        assert result == [EpisodeKey(season=2, episode=3)]

    def test_removes_duplicates(self):
        episodes = [_episode("a", 1, 1), _episode("b", 1, 1), _episode("c", 1, 2)]
        with patch(REQUESTS_GET, side_effect=_two_step([_series(SERIES_ID, 1396)], episodes)):
            result = jellyfin.list_library_episodes(SERIES_TMDB_ID)

        assert result == [EpisodeKey(season=1, episode=1), EpisodeKey(season=1, episode=2)]

    def test_sorts_by_season_then_episode(self):
        episodes = [
            _episode("a", 2, 1),
            _episode("b", 1, 10),
            _episode("c", 1, 2),
            _episode("d", 1, 1),
        ]
        with patch(REQUESTS_GET, side_effect=_two_step([_series(SERIES_ID, 1396)], episodes)):
            result = jellyfin.list_library_episodes(SERIES_TMDB_ID)

        assert result == [
            EpisodeKey(season=1, episode=1),
            EpisodeKey(season=1, episode=2),
            EpisodeKey(season=1, episode=10),
            EpisodeKey(season=2, episode=1),
        ]

    def test_raises_jellyfin_unavailable_on_series_error_response(self):
        with (
            patch(REQUESTS_GET, return_value=_jellyfin_503()),
            pytest.raises(AppException) as exc_info,
        ):
            jellyfin.list_library_episodes(SERIES_TMDB_ID)

        assert exc_info.value.code == ErrorCode.JELLYFIN_UNAVAILABLE

    def test_raises_jellyfin_unavailable_on_episodes_error_response(self):
        responses = [_jellyfin_items([_series(SERIES_ID, 1396)]), _jellyfin_503()]
        with (
            patch(REQUESTS_GET, side_effect=responses),
            pytest.raises(AppException) as exc_info,
        ):
            jellyfin.list_library_episodes(SERIES_TMDB_ID)

        assert exc_info.value.code == ErrorCode.JELLYFIN_UNAVAILABLE


class TestLibraryEpisodesRoute:
    def test_returns_the_contract_shape(self, client):
        keys = [EpisodeKey(season=1, episode=1), EpisodeKey(season=1, episode=2)]
        with patch(SERVICE_FN, return_value=keys) as mock_service:
            response = client.get(EPISODES_URL, params={"tmdb_id": SERIES_TMDB_ID})

        assert response.status_code == 200
        body = LibraryEpisodesResponse.model_validate(response.json())
        assert body.tmdb_id == SERIES_TMDB_ID
        assert body.episodes == keys
        mock_service.assert_called_once_with(SERIES_TMDB_ID)

    def test_returns_empty_list_for_unknown_series(self, client):
        with patch(SERVICE_FN, return_value=[]):
            response = client.get(EPISODES_URL, params={"tmdb_id": SERIES_TMDB_ID})

        assert response.status_code == 200
        assert response.json() == {"tmdb_id": SERIES_TMDB_ID, "episodes": []}

    def test_requires_tmdb_id(self, client):
        response = client.get(EPISODES_URL)

        assert response.status_code == 422

    def test_rejects_non_integer_tmdb_id(self, client):
        response = client.get(EPISODES_URL, params={"tmdb_id": "abc"})

        assert response.status_code == 422

    def test_requires_api_key(self, unauthed_client):
        response = unauthed_client.get(EPISODES_URL, params={"tmdb_id": SERIES_TMDB_ID})

        assert response.status_code == 403

    def test_returns_503_when_jellyfin_unavailable(self, client):
        with patch(REQUESTS_GET, return_value=_jellyfin_503()):
            response = client.get(EPISODES_URL, params={"tmdb_id": SERIES_TMDB_ID})

        assert response.status_code == 503
        assert response.json()["code"] == "JELLYFIN_UNAVAILABLE"

    def test_includes_request_id_header(self, client):
        with patch(SERVICE_FN, return_value=[]):
            response = client.get(EPISODES_URL, params={"tmdb_id": SERIES_TMDB_ID})

        assert "X-Request-ID" in response.headers
