# CLAUDE.md - medialab-jellyfin

Workspace rules, conventions, standards and workflow live in the root
[`medialab/CLAUDE.md`](../CLAUDE.md); it is the authority when anything here
disagrees. This file holds only what is specific to this code.

## Commands

```bash
uv sync --dev
uv run medialab-jellyfin        # production
uv run medialab-jellyfin-dev    # dev, hot-reload
uv run pytest
uv run pytest tests/test_system.py::TestHealthCheck::test_returns_uptime
```

## Config

`.env.example` is the authoritative variable list; `core/config.py` holds the
defaults. Every field is optional at import time and required at runtime.
Inside a container `JELLYFIN_HOST` must be `host.docker.internal`, not
`127.0.0.1` (that would be the container itself).

## Architecture

Thin FastAPI proxy over the Jellyfin server API. It assumes Jellyfin is
reachable; availability and workflow belong to the orchestrator. Endpoint
table: [README](README.md).

**Library resolution (`POST /library/paths`):** the target library is
discovered dynamically from `GET /Library/VirtualFolders` filtered by
`CollectionType` (`movie` -> `movies`, `show` -> `tvshows`). Exactly one match
is used; `library_name` overrides discovery; zero or several matches without
an override return a structured error. Jellyfin stays the source of truth for
library names, so no `JELLYFIN_*_LIBRARY` env vars exist. This endpoint is for
one-time setup; the per-download pipeline only calls `/library/scan`.

**Discover placeholders:** folders under `DISCOVER_MOUNT_PATH`, found by
their `[tmdbid-<id>]` suffix so a title change never renames a folder. The
`.nfo` carries the display title (with the state suffix) for Jellyfin and
`medialab_title` / `medialab_state` for listing. After writes the whole
Discover library is refreshed by item id (`/Items/{id}/Refresh`); that picks
up adds, removals and `.nfo` edits without knowing the host-side path, so no
path translation exists here.

**Cross-cutting:** `X-API-Key` via `Security(APIKeyHeader)` in `core/auth.py`,
applied on `include_router` (system router public so `/health` needs no key).
`slowapi` `RATE_LIMIT_DEFAULT` in `core/limiter.py`, `/health` exempt.
`RequestLoggingMiddleware` adds `X-Request-ID`. Errors are `AppException` +
`ErrorCode`.

## Module layout

```
src/medialab_jellyfin/
├── core/        config, auth, limiter, middleware, logger, errors, constants
├── services/    jellyfin (client, reachability, library operations, Discover
│                library ids, item refresh, user favorites),
│                placeholders (Discover folders on disk: .nfo + clip copy)
├── schemas/     library (scan/paths/items request + response, Jellyfin DTOs),
│                discover, system, errors
├── assets/      request.mp4, the clip every placeholder copies
├── routers/     system, library, discover (registered in main.py under /api/v1)
└── main.py      app, middleware, exception handlers, custom OpenAPI
```

## Testing patterns

- `conftest.py` autouse fixtures: `patch_api_key` and `reset_rate_limiter`.
- `client` fixture sends `X-API-Key`; `unauthed_client` for rejection tests.
- Patch `medialab_jellyfin.core.auth.config` (not `core.config`) for auth;
  patch `medialab_jellyfin.core.middleware.app_logger` for log assertions.
- Jellyfin is mocked at the service boundary. Nothing live.
