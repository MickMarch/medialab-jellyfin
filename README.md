# medialab-jellyfin

FastAPI microservice wrapping the Jellyfin media server API for the
[medialab](https://github.com/MickMarch/medialab) suite. Triggers library
scans, registers library paths, and searches items. It is a downstream worker:
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
