"""Tests for the Discover placeholder and favorites endpoints and their Jellyfin calls."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from medialab_contracts import (
    DISCOVER_LIBRARY_NAMES,
    JellyfinRequestEvent,
    MediaType,
    PlaceholderState,
)

from medialab_jellyfin.core.errors import AppException, ErrorCode
from medialab_jellyfin.schemas.discover import FavoriteScope
from medialab_jellyfin.services import jellyfin, placeholders

PLACEHOLDER_URL = "/api/v1/discover/placeholders"
REFRESH_URL = "/api/v1/discover/refresh"
FAVORITES_URL = "/api/v1/discover/favorites"
ROUTER = "medialab_jellyfin.routers.discover"
REQUESTS_GET = "medialab_jellyfin.services.jellyfin.requests.get"
REQUESTS_POST = "medialab_jellyfin.services.jellyfin.requests.post"

MOVIE_LIB_ID = "lib-movies"
SHOW_LIB_ID = "lib-shows"
LIBRARY_IDS = {MediaType.MOVIE: MOVIE_LIB_ID, MediaType.SHOW: SHOW_LIB_ID}
USER_ID = "user-1"
TMDB_ID = 238
BODY = {"title": "The Godfather", "year": 1972, "state": "requested"}


def _ok(json_body: object = None) -> MagicMock:
    mock = MagicMock()
    mock.status_code = 200
    mock.ok = True
    mock.json.return_value = json_body
    return mock


def _item(item_id: str, item_type: str, tmdb: str | None) -> dict[str, object]:
    providers = {"Tmdb": tmdb} if tmdb is not None else {}
    return {"Id": item_id, "Name": item_id, "Type": item_type, "ProviderIds": providers}


@pytest.fixture
def discover_root(tmp_path: Path, mocker) -> Path:
    mocker.patch(f"{ROUTER}.config", discover_mount_path=str(tmp_path))
    return tmp_path


@pytest.fixture
def refresh(mocker) -> MagicMock:
    mocker.patch(f"{ROUTER}.jellyfin.discover_library_ids", return_value=LIBRARY_IDS)
    return mocker.patch(f"{ROUTER}.jellyfin.refresh_item")


class TestPutPlaceholder:
    def test_writes_and_refreshes_the_type_library(
        self, client: TestClient, discover_root: Path, refresh: MagicMock
    ) -> None:
        response = client.put(f"{PLACEHOLDER_URL}/movie/{TMDB_ID}", json=BODY)
        assert response.status_code == 204
        [info] = placeholders.list_placeholders(discover_root, MediaType.MOVIE)
        assert info.state is PlaceholderState.REQUESTED
        refresh.assert_called_once_with(MOVIE_LIB_ID)

    def test_unchanged_write_does_not_refresh(
        self, client: TestClient, discover_root: Path, refresh: MagicMock
    ) -> None:
        client.put(f"{PLACEHOLDER_URL}/movie/{TMDB_ID}", json=BODY)
        refresh.reset_mock()
        assert client.put(f"{PLACEHOLDER_URL}/movie/{TMDB_ID}", json=BODY).status_code == 204
        refresh.assert_not_called()

    def test_refresh_false_skips_the_refresh(
        self, client: TestClient, discover_root: Path, refresh: MagicMock
    ) -> None:
        response = client.put(
            f"{PLACEHOLDER_URL}/movie/{TMDB_ID}", json=BODY, params={"refresh": "false"}
        )
        assert response.status_code == 204
        refresh.assert_not_called()

    def test_blank_title_is_422(
        self, client: TestClient, discover_root: Path, refresh: MagicMock
    ) -> None:
        response = client.put(f"{PLACEHOLDER_URL}/movie/{TMDB_ID}", json={**BODY, "title": " "})
        assert response.status_code == 422

    def test_unconfigured_mount_is_503(self, client: TestClient, mocker) -> None:
        mocker.patch(f"{ROUTER}.config", discover_mount_path=None)
        response = client.put(f"{PLACEHOLDER_URL}/movie/{TMDB_ID}", json=BODY)
        assert response.status_code == 503
        assert response.json()["code"] == ErrorCode.DISCOVER_NOT_CONFIGURED.value


class TestDeletePlaceholder:
    def test_removes_and_refreshes(
        self, client: TestClient, discover_root: Path, refresh: MagicMock
    ) -> None:
        client.put(f"{PLACEHOLDER_URL}/show/{TMDB_ID}", json=BODY)
        refresh.reset_mock()
        assert client.delete(f"{PLACEHOLDER_URL}/show/{TMDB_ID}").status_code == 204
        assert placeholders.list_placeholders(discover_root, MediaType.SHOW) == []
        refresh.assert_called_once_with(SHOW_LIB_ID)

    def test_absent_is_204_without_refresh(
        self, client: TestClient, discover_root: Path, refresh: MagicMock
    ) -> None:
        assert client.delete(f"{PLACEHOLDER_URL}/movie/{TMDB_ID}").status_code == 204
        refresh.assert_not_called()


class TestListPlaceholders:
    def test_lists_by_media_type(
        self, client: TestClient, discover_root: Path, refresh: MagicMock
    ) -> None:
        client.put(f"{PLACEHOLDER_URL}/movie/{TMDB_ID}", json=BODY)
        body = client.get(PLACEHOLDER_URL, params={"media_type": "movie"}).json()
        assert body["media_type"] == "movie"
        assert body["placeholders"] == [
            {"tmdb_id": TMDB_ID, "title": "The Godfather", "state": "requested"}
        ]


class TestRefreshRoute:
    def test_refreshes_one_type(self, client: TestClient, refresh: MagicMock) -> None:
        assert client.post(REFRESH_URL, params={"media_type": "show"}).status_code == 204
        refresh.assert_called_once_with(SHOW_LIB_ID)


class TestFavoritesRoute:
    def test_returns_request_events(self, client: TestClient, mocker) -> None:
        event = JellyfinRequestEvent(
            jellyfin_user_id=USER_ID, item_id="i", item_type="Movie", tmdb_id=1, is_favorite=True
        )
        spy = mocker.patch(f"{ROUTER}.jellyfin.list_favorites", return_value=[event])
        response = client.get(FAVORITES_URL, params={"user_id": USER_ID, "scope": "library"})
        assert response.status_code == 200
        assert response.json() == [event.model_dump(mode="json", by_alias=True)]
        spy.assert_called_once_with(USER_ID, FavoriteScope.LIBRARY)

    def test_scope_defaults_to_discover(self, client: TestClient, mocker) -> None:
        spy = mocker.patch(f"{ROUTER}.jellyfin.list_favorites", return_value=[])
        client.get(FAVORITES_URL, params={"user_id": USER_ID})
        spy.assert_called_once_with(USER_ID, FavoriteScope.DISCOVER)


class TestDiscoverLibraryIds:
    def test_maps_library_names_to_item_ids(self) -> None:
        folders = [
            {"Name": DISCOVER_LIBRARY_NAMES[MediaType.MOVIE], "ItemId": MOVIE_LIB_ID},
            {"Name": DISCOVER_LIBRARY_NAMES[MediaType.SHOW], "ItemId": SHOW_LIB_ID},
            {"Name": "Movies", "ItemId": "real", "CollectionType": "movies"},
        ]
        with patch(REQUESTS_GET, return_value=_ok(folders)):
            assert jellyfin.discover_library_ids() == LIBRARY_IDS

    def test_missing_library_is_library_not_found(self) -> None:
        folders = [{"Name": DISCOVER_LIBRARY_NAMES[MediaType.MOVIE], "ItemId": MOVIE_LIB_ID}]
        with patch(REQUESTS_GET, return_value=_ok(folders)), pytest.raises(AppException) as exc:
            jellyfin.discover_library_ids()
        assert exc.value.code is ErrorCode.LIBRARY_NOT_FOUND


class TestRefreshItem:
    def test_posts_a_recursive_refresh(self) -> None:
        with patch(REQUESTS_POST, return_value=_ok()) as post:
            jellyfin.refresh_item(MOVIE_LIB_ID)
        url = post.call_args.args[0]
        assert url.endswith(f"/Items/{MOVIE_LIB_ID}/Refresh")
        assert post.call_args.kwargs["params"]["Recursive"] == "true"


class TestListFavorites:
    def _patch(self, mocker, discover_items: dict[str, list], all_items: list) -> MagicMock:
        mocker.patch.object(jellyfin, "discover_library_ids", return_value=LIBRARY_IDS)

        def fake_get(url, headers, params, timeout):
            parent = params.get("ParentId")
            items = discover_items.get(parent, []) if parent else all_items
            return _ok({"Items": items, "TotalRecordCount": len(items)})

        return mocker.patch(REQUESTS_GET, side_effect=fake_get)

    def test_discover_scope_reads_both_discover_libraries(self, mocker) -> None:
        get = self._patch(
            mocker,
            {
                MOVIE_LIB_ID: [_item("m1", "Movie", "238")],
                SHOW_LIB_ID: [_item("s1", "Series", "95396")],
            },
            [],
        )
        events = jellyfin.list_favorites(USER_ID, FavoriteScope.DISCOVER)
        assert [(e.item_id, e.media_type, e.tmdb_id) for e in events] == [
            ("m1", MediaType.MOVIE, 238),
            ("s1", MediaType.SHOW, 95396),
        ]
        assert all(e.is_favorite and e.jellyfin_user_id == USER_ID for e in events)
        url = get.call_args.args[0]
        assert f"/Users/{USER_ID}/Items" in url
        assert get.call_args.kwargs["params"]["Filters"] == "IsFavorite"

    def test_library_scope_excludes_discover_items(self, mocker) -> None:
        self._patch(
            mocker,
            {MOVIE_LIB_ID: [_item("m1", "Movie", "238")], SHOW_LIB_ID: []},
            [_item("m1", "Movie", "238"), _item("real", "Movie", "603")],
        )
        events = jellyfin.list_favorites(USER_ID, FavoriteScope.LIBRARY)
        assert [(e.item_id, e.tmdb_id) for e in events] == [("real", 603)]

    def test_items_without_a_tmdb_id_are_skipped(self, mocker) -> None:
        self._patch(
            mocker,
            {MOVIE_LIB_ID: [_item("m1", "Movie", None), _item("m2", "Movie", "x")]},
            [],
        )
        assert jellyfin.list_favorites(USER_ID, FavoriteScope.DISCOVER) == []
