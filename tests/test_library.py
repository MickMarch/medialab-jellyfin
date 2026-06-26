"""Tests for the library router: scan, paths, and items endpoints."""

from unittest.mock import MagicMock, patch

SCAN_URL = "/api/v1/library/scan"
PATHS_URL = "/api/v1/library/paths"
ITEMS_URL = "/api/v1/library/items"

VIRTUAL_FOLDERS_MOVIES = [
    {"Name": "Movies", "CollectionType": "movies"},
    {"Name": "TV Shows", "CollectionType": "tvshows"},
]

VIRTUAL_FOLDERS_AMBIGUOUS = [
    {"Name": "Movies", "CollectionType": "movies"},
    {"Name": "Kids Movies", "CollectionType": "movies"},
]


def _jellyfin_204():
    mock = MagicMock()
    mock.status_code = 204
    mock.ok = True
    return mock


def _jellyfin_virtual_folders(folders):
    mock = MagicMock()
    mock.status_code = 200
    mock.ok = True
    mock.json.return_value = folders
    return mock


def _jellyfin_items_response(items, total):
    mock = MagicMock()
    mock.status_code = 200
    mock.ok = True
    mock.json.return_value = {"Items": items, "TotalRecordCount": total}
    return mock


def _jellyfin_503():
    mock = MagicMock()
    mock.status_code = 503
    mock.ok = False
    return mock


class TestLibraryScan:
    def test_scan_returns_204(self, client):
        with patch(
            "medialab_jellyfin.services.jellyfin.requests.post", return_value=_jellyfin_204()
        ):
            response = client.post(
                SCAN_URL, json={"path": "/data/movies/Foo (2024)", "update_type": "Created"}
            )

        assert response.status_code == 204

    def test_scan_forwards_correct_payload_to_jellyfin(self, client):
        with patch(
            "medialab_jellyfin.services.jellyfin.requests.post", return_value=_jellyfin_204()
        ) as mock_post:
            client.post(
                SCAN_URL, json={"path": "/data/movies/Foo (2024)", "update_type": "Modified"}
            )

        _, kwargs = mock_post.call_args
        body = kwargs["json"]
        assert body == {"Updates": [{"Path": "/data/movies/Foo (2024)", "UpdateType": "Modified"}]}

    def test_scan_defaults_update_type_to_created(self, client):
        with patch(
            "medialab_jellyfin.services.jellyfin.requests.post", return_value=_jellyfin_204()
        ) as mock_post:
            client.post(SCAN_URL, json={"path": "/data/movies/Foo (2024)"})

        _, kwargs = mock_post.call_args
        assert kwargs["json"]["Updates"][0]["UpdateType"] == "Created"

    def test_scan_rejects_invalid_update_type(self, client):
        response = client.post(
            SCAN_URL, json={"path": "/data/movies/Foo (2024)", "update_type": "Invalid"}
        )

        assert response.status_code == 422

    def test_scan_rejects_empty_path(self, client):
        response = client.post(SCAN_URL, json={"path": ""})

        assert response.status_code == 422

    def test_scan_rejects_whitespace_path(self, client):
        response = client.post(SCAN_URL, json={"path": "   "})

        assert response.status_code == 422

    def test_scan_requires_api_key(self, unauthed_client):
        response = unauthed_client.post(SCAN_URL, json={"path": "/data/movies/Foo (2024)"})

        assert response.status_code == 403

    def test_scan_returns_503_when_jellyfin_unavailable(self, client):
        with patch(
            "medialab_jellyfin.services.jellyfin.requests.post", return_value=_jellyfin_503()
        ):
            response = client.post(SCAN_URL, json={"path": "/data/movies/Foo (2024)"})

        assert response.status_code == 503
        assert response.json()["code"] == "JELLYFIN_UNAVAILABLE"

    def test_scan_includes_request_id_header(self, client):
        with patch(
            "medialab_jellyfin.services.jellyfin.requests.post", return_value=_jellyfin_204()
        ):
            response = client.post(SCAN_URL, json={"path": "/data/movies/Foo (2024)"})

        assert "X-Request-ID" in response.headers


class TestLibraryPaths:
    def test_add_path_returns_204(self, client):
        with (
            patch(
                "medialab_jellyfin.services.jellyfin.requests.get",
                return_value=_jellyfin_virtual_folders(VIRTUAL_FOLDERS_MOVIES),
            ),
            patch(
                "medialab_jellyfin.services.jellyfin.requests.post", return_value=_jellyfin_204()
            ),
        ):
            response = client.post(
                PATHS_URL, json={"media_type": "movie", "path": "/data/movies/Foo (2024)"}
            )

        assert response.status_code == 204

    def test_add_path_resolves_movie_library(self, client):
        with (
            patch(
                "medialab_jellyfin.services.jellyfin.requests.get",
                return_value=_jellyfin_virtual_folders(VIRTUAL_FOLDERS_MOVIES),
            ),
            patch(
                "medialab_jellyfin.services.jellyfin.requests.post", return_value=_jellyfin_204()
            ) as mock_post,
        ):
            client.post(PATHS_URL, json={"media_type": "movie", "path": "/data/movies/Foo (2024)"})

        _, kwargs = mock_post.call_args
        assert kwargs["json"]["Name"] == "Movies"
        assert kwargs["json"]["Path"] == "/data/movies/Foo (2024)"

    def test_add_path_resolves_show_library(self, client):
        with (
            patch(
                "medialab_jellyfin.services.jellyfin.requests.get",
                return_value=_jellyfin_virtual_folders(VIRTUAL_FOLDERS_MOVIES),
            ),
            patch(
                "medialab_jellyfin.services.jellyfin.requests.post", return_value=_jellyfin_204()
            ) as mock_post,
        ):
            client.post(PATHS_URL, json={"media_type": "show", "path": "/data/tvshows/Bar"})

        _, kwargs = mock_post.call_args
        assert kwargs["json"]["Name"] == "TV Shows"

    def test_add_path_refresh_library_param_forwarded(self, client):
        with (
            patch(
                "medialab_jellyfin.services.jellyfin.requests.get",
                return_value=_jellyfin_virtual_folders(VIRTUAL_FOLDERS_MOVIES),
            ),
            patch(
                "medialab_jellyfin.services.jellyfin.requests.post", return_value=_jellyfin_204()
            ) as mock_post,
        ):
            client.post(
                PATHS_URL,
                json={
                    "media_type": "movie",
                    "path": "/data/movies/Foo (2024)",
                    "refresh_library": True,
                },
            )

        _, kwargs = mock_post.call_args
        assert kwargs["params"]["refreshLibrary"] is True

    def test_add_path_refresh_library_defaults_false(self, client):
        with (
            patch(
                "medialab_jellyfin.services.jellyfin.requests.get",
                return_value=_jellyfin_virtual_folders(VIRTUAL_FOLDERS_MOVIES),
            ),
            patch(
                "medialab_jellyfin.services.jellyfin.requests.post", return_value=_jellyfin_204()
            ) as mock_post,
        ):
            client.post(PATHS_URL, json={"media_type": "movie", "path": "/data/movies/Foo (2024)"})

        _, kwargs = mock_post.call_args
        assert kwargs["params"]["refreshLibrary"] is False

    def test_add_path_library_name_override_skips_discovery(self, client):
        with (
            patch("medialab_jellyfin.services.jellyfin.requests.get") as mock_get,
            patch(
                "medialab_jellyfin.services.jellyfin.requests.post", return_value=_jellyfin_204()
            ) as mock_post,
        ):
            client.post(
                PATHS_URL,
                json={
                    "media_type": "movie",
                    "path": "/data/movies/Foo (2024)",
                    "library_name": "My Films",
                },
            )

        mock_get.assert_not_called()
        _, kwargs = mock_post.call_args
        assert kwargs["json"]["Name"] == "My Films"

    def test_add_path_returns_404_when_no_matching_library(self, client):
        folders = [{"Name": "Music", "CollectionType": "music"}]
        with patch(
            "medialab_jellyfin.services.jellyfin.requests.get",
            return_value=_jellyfin_virtual_folders(folders),
        ):
            response = client.post(
                PATHS_URL, json={"media_type": "movie", "path": "/data/movies/Foo (2024)"}
            )

        assert response.status_code == 404
        assert response.json()["code"] == "LIBRARY_NOT_FOUND"

    def test_add_path_returns_409_when_ambiguous_library(self, client):
        with patch(
            "medialab_jellyfin.services.jellyfin.requests.get",
            return_value=_jellyfin_virtual_folders(VIRTUAL_FOLDERS_AMBIGUOUS),
        ):
            response = client.post(
                PATHS_URL, json={"media_type": "movie", "path": "/data/movies/Foo (2024)"}
            )

        assert response.status_code == 409
        assert response.json()["code"] == "LIBRARY_AMBIGUOUS"

    def test_add_path_rejects_empty_path(self, client):
        response = client.post(PATHS_URL, json={"media_type": "movie", "path": ""})

        assert response.status_code == 422

    def test_add_path_rejects_whitespace_path(self, client):
        response = client.post(PATHS_URL, json={"media_type": "movie", "path": "   "})

        assert response.status_code == 422

    def test_add_path_rejects_empty_library_name(self, client):
        response = client.post(
            PATHS_URL,
            json={"media_type": "movie", "path": "/data/movies/Foo (2024)", "library_name": ""},
        )

        assert response.status_code == 422

    def test_add_path_rejects_whitespace_library_name(self, client):
        response = client.post(
            PATHS_URL,
            json={"media_type": "movie", "path": "/data/movies/Foo (2024)", "library_name": "   "},
        )

        assert response.status_code == 422

    def test_add_path_requires_api_key(self, unauthed_client):
        response = unauthed_client.post(
            PATHS_URL, json={"media_type": "movie", "path": "/data/movies/Foo (2024)"}
        )

        assert response.status_code == 403

    def test_add_path_returns_503_when_jellyfin_unavailable(self, client):
        with patch(
            "medialab_jellyfin.services.jellyfin.requests.get", return_value=_jellyfin_503()
        ):
            response = client.post(
                PATHS_URL, json={"media_type": "movie", "path": "/data/movies/Foo (2024)"}
            )

        assert response.status_code == 503
        assert response.json()["code"] == "JELLYFIN_UNAVAILABLE"

    def test_add_path_includes_request_id_header(self, client):
        with (
            patch(
                "medialab_jellyfin.services.jellyfin.requests.get",
                return_value=_jellyfin_virtual_folders(VIRTUAL_FOLDERS_MOVIES),
            ),
            patch(
                "medialab_jellyfin.services.jellyfin.requests.post", return_value=_jellyfin_204()
            ),
        ):
            response = client.post(
                PATHS_URL, json={"media_type": "movie", "path": "/data/movies/Foo (2024)"}
            )

        assert "X-Request-ID" in response.headers


class TestLibraryItems:
    def test_items_returns_200_with_results(self, client):
        items = [{"Id": "abc123", "Name": "Foo", "Type": "Movie"}]
        with patch(
            "medialab_jellyfin.services.jellyfin.requests.get",
            return_value=_jellyfin_items_response(items, 1),
        ):
            response = client.get(ITEMS_URL, params={"search_term": "Foo"})

        assert response.status_code == 200
        body = response.json()
        assert body["total_record_count"] == 1
        assert len(body["items"]) == 1
        assert body["items"][0]["name"] == "Foo"

    def test_items_forwards_search_term(self, client):
        with patch(
            "medialab_jellyfin.services.jellyfin.requests.get",
            return_value=_jellyfin_items_response([], 0),
        ) as mock_get:
            client.get(ITEMS_URL, params={"search_term": "Breaking Bad"})

        _, kwargs = mock_get.call_args
        assert kwargs["params"]["searchTerm"] == "Breaking Bad"

    def test_items_forwards_include_item_types(self, client):
        with patch(
            "medialab_jellyfin.services.jellyfin.requests.get",
            return_value=_jellyfin_items_response([], 0),
        ) as mock_get:
            client.get(ITEMS_URL, params={"include_item_types": "Series"})

        _, kwargs = mock_get.call_args
        assert kwargs["params"]["includeItemTypes"] == "Series"

    def test_items_forwards_limit(self, client):
        with patch(
            "medialab_jellyfin.services.jellyfin.requests.get",
            return_value=_jellyfin_items_response([], 0),
        ) as mock_get:
            client.get(ITEMS_URL, params={"limit": 10})

        _, kwargs = mock_get.call_args
        assert kwargs["params"]["limit"] == 10

    def test_items_recursive_defaults_true(self, client):
        with patch(
            "medialab_jellyfin.services.jellyfin.requests.get",
            return_value=_jellyfin_items_response([], 0),
        ) as mock_get:
            client.get(ITEMS_URL)

        _, kwargs = mock_get.call_args
        assert kwargs["params"]["recursive"] is True

    def test_items_requires_api_key(self, unauthed_client):
        response = unauthed_client.get(ITEMS_URL)

        assert response.status_code == 403

    def test_items_returns_503_when_jellyfin_unavailable(self, client):
        with patch(
            "medialab_jellyfin.services.jellyfin.requests.get", return_value=_jellyfin_503()
        ):
            response = client.get(ITEMS_URL)

        assert response.status_code == 503
        assert response.json()["code"] == "JELLYFIN_UNAVAILABLE"

    def test_items_includes_request_id_header(self, client):
        with patch(
            "medialab_jellyfin.services.jellyfin.requests.get",
            return_value=_jellyfin_items_response([], 0),
        ):
            response = client.get(ITEMS_URL)

        assert "X-Request-ID" in response.headers

    def test_items_returns_empty_list_when_no_results(self, client):
        with patch(
            "medialab_jellyfin.services.jellyfin.requests.get",
            return_value=_jellyfin_items_response([], 0),
        ):
            response = client.get(ITEMS_URL, params={"search_term": "nonexistent"})

        assert response.status_code == 200
        body = response.json()
        assert body["items"] == []
        assert body["total_record_count"] == 0
