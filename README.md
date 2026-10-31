# medialab-jellyfin

FastAPI microservice wrapping the Jellyfin media server API for the
[medialab](https://github.com/MickMarch/medialab) suite. Triggers library
scans, registers library paths, searches items, and lists the TMDB ids and
episodes in the library. It is a downstream worker:
only the medialab-orchestrator calls it.

## Prerequisites

Install and run [Jellyfin](https://jellyfin.org/downloads). In the dashboard,
**Administration > API Keys**, generate a key. Note the host and port
(default `8096`).

## Setup

```bash
uv sync --dev
cp .env.example .env     # then fill in the values
uv run medialab-jellyfin-dev   # dev, hot-reload
uv run medialab-jellyfin       # production
```

`.env.example` documents every variable. Interactive docs at `/docs`.

The service runs as a container from the workspace `docker-compose.yml`; see
the [workspace README](../README.md). Inside a container `JELLYFIN_HOST` must be
`host.docker.internal`.

## API

All paths under `/api/v1`. Every endpoint except `/health` requires
`X-API-Key: <API_KEY>`; a missing or wrong key returns `403` with
`"code": "UNAUTHORIZED"`.

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/health` | Public. Uptime and Jellyfin reachability. |
| `POST` | `/library/scan` | Body `{path, update_type?}` (`Created` default, `Modified`, `Deleted`). Forwards to Jellyfin `POST /Library/Media/Updated`. Returns `204`. |
| `POST` | `/library/paths` | Body `{media_type, path, refresh_library?, library_name?}`. Adds a directory to the matching library (`POST /Library/VirtualFolders/Paths`). Library resolved from `media_type` via `GET /Library/VirtualFolders`; `library_name` overrides; ambiguous or missing returns `LIBRARY_AMBIGUOUS` / `LIBRARY_NOT_FOUND`. Setup-time use, not per download. |
| `GET` | `/library/items` | Query `search_term`, `include_item_types`, `recursive`, `parent_id`, `limit`. Passthrough of a small `GET /Items` subset, reshaped to `{items, total_record_count}`. |
| `GET` | `/library/tmdb-ids` | Query `media_type` (`movie` or `show`). TMDB ids of every Movie or Series item (`GET /Items` with `ProviderIds`), deduplicated; items without a numeric TMDB id are skipped. Returns `{media_type, tmdb_ids}`. |
| `GET` | `/library/episodes` | Query `tmdb_id` (int). Finds the Series item with that TMDB id, then lists its Episode items (`GET /Items?ParentId=<series>` with `ParentIndexNumber,IndexNumber`); items missing either number are skipped. Returns `{tmdb_id, episodes: [{season, episode}]}`, deduplicated and sorted; an unknown series returns an empty list. |

### Discover

Placeholder folders for requesting titles from inside Jellyfin clients
([spec](../docs/specs/jellyfin-in-app-requests.md)). Folders live under
`DISCOVER_MOUNT_PATH`; the two Discover libraries must already exist in
Jellyfin under the names in `DISCOVER_LIBRARY_NAMES` (`LIBRARY_NOT_FOUND`
otherwise). Without `DISCOVER_MOUNT_PATH` the placeholder routes return
`503 DISCOVER_NOT_CONFIGURED`.

| Method | Endpoint | Description |
|---|---|---|
| `PUT` | `/discover/placeholders/{media_type}/{tmdb_id}` | Body `{title, year?, state?}`. Creates `<Title> (<Year>) [tmdbid-<id>]/` with an `.nfo` (display title carries the state suffix) and a copy of the request clip, or rewrites the `.nfo` when anything changed. Refreshes that Discover library when something was written, unless `?refresh=false`. `204`. |
| `DELETE` | `/discover/placeholders/{media_type}/{tmdb_id}` | Removes the folder and refreshes; absent is `204` with no refresh. Takes `?refresh=false`. |
| `GET` | `/discover/placeholders` | Query `media_type`. `{media_type, placeholders: [{tmdb_id, title, state}]}` read from the `.nfo` files. |
| `POST` | `/discover/refresh` | Query `media_type`. Rescans one Discover library; for after a batch of `refresh=false` writes. `204`. |
| `GET` | `/discover/favorites` | Query `user_id`, `scope` (`discover` default, or `library`). The user's favorited movies and series with a TMDB id as `JellyfinRequestEvent`s: on placeholders (requests), or on everything outside Discover (recommendation seeds). |

The clip is written to `<DISCOVER_MOUNT_PATH>/_clip/request.mp4` from the
bundled asset only when absent, so a custom clip can replace it.

Errors: `{"status": "error", "code": "<ErrorCode>", "detail": "..."}`. Rate
limit 60/min per IP; `429` carries `Retry-After`. Every response includes an
`X-Request-ID` UUID.

## Development

```bash
uv run pytest
uv run ruff check . && uv run ruff format --check . && uv run mypy src
```

Standards, workflow and release process: [workspace CLAUDE.md](../CLAUDE.md).
Code-local notes: [CLAUDE.md](CLAUDE.md).
