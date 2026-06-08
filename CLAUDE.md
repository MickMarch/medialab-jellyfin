# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
# Install dependencies
uv sync --dev

# Run API (production)
uv run medialab-jellyfin

# Run API (dev, hot-reload)
uv run medialab-jellyfin-dev

# Run all tests
uv run pytest

# Run single test
uv run pytest tests/test_system.py::TestHealthCheck::test_returns_uptime
```

## Environment Setup

Copy `.env.example` to `.env` and populate. All config loads via `pydantic-settings` from `.env`.

All fields are optional at import time (for CI compatibility), but the service will not function correctly without real values at runtime.

- `JELLYFIN_API_KEY` — Jellyfin API key, generated in the Jellyfin dashboard under Administration → API Keys
- `API_KEY` — static key required in `X-API-Key` header on all protected endpoints

Optional (defaults shown):
- `JELLYFIN_HOST=127.0.0.1`, `JELLYFIN_PORT=8096`
- `API_HOST=0.0.0.0`, `API_PORT=8001`

## Architecture

FastAPI REST API wrapping the Jellyfin media server API. Status: scaffolding only — library endpoints (scan trigger, add path to library) not yet implemented.

**Auth:** All endpoints except `/api/v1/health` require `X-API-Key: <API_KEY>`. Implemented in `core/auth.py` via FastAPI `Security(APIKeyHeader)`. Missing key → 403 with `UNAUTHORIZED` code. Wrong key → 403 with `UNAUTHORIZED` code. Applied via `dependencies=[Depends(verify_api_key)]` on `include_router` calls in `main.py`; system routes stay public so `/health` is reachable without a key.

**Rate limiting:** `slowapi` limiter in `core/limiter.py`. All endpoints: `RATE_LIMIT_DEFAULT` (60/min). `/health` exempt via `@limiter.exempt`. Applied via `@limiter.limit(RATE_LIMIT_DEFAULT)` decorator on each route handler. Breach returns 429 with `Retry-After` header and `RATE_LIMITED` error code. Limiter storage must be reset between tests - see `reset_rate_limiter` fixture in `conftest.py`.

**Request logging:** `core/middleware.py` - `RequestLoggingMiddleware` logs method, path+query, status, duration on every request. Injects `X-Request-ID` UUID response header per request for cross-service correlation.

**Error handling:** `core/errors.py` defines `ErrorCode` enum and `AppException`. All structured errors use shape `{"status": "error", "code": "<ErrorCode>", "detail": "..."}`. Exception handlers registered in `main.py` for `AppException`, `RequestValidationError`, and `RateLimitExceeded`. `schemas/errors.py` holds `ErrorResponse` Pydantic model used in `responses=` on route decorators for OpenAPI documentation.

**Module layout:**
- `core/config.py` — single `AppConfig` pydantic-settings instance (`config`) imported everywhere
- `core/auth.py` — `verify_api_key` FastAPI dependency; patch `medialab_jellyfin.core.auth.config` in tests
- `core/limiter.py` — `limiter` slowapi instance, `RATE_LIMIT_DEFAULT` constant
- `core/middleware.py` — `RequestLoggingMiddleware` (BaseHTTPMiddleware)
- `core/logger.py` — `app_logger` singleton; stdout only (no file handler - correct for containers)
- `core/errors.py` — `ErrorCode` enum, `AppException`
- `services/jellyfin.py` — Jellyfin API client: connection setup, reachability checks, library operations
- `schemas/` — Pydantic models for request/response validation; `errors.py` holds shared `ErrorResponse`
- `routers/` — APIRouter modules grouped by domain (`system`); registered in `main.py` via `include_router` with `prefix="/api/v1"`
- `main.py` — FastAPI app instantiation, middleware stack, exception handlers, router registration, custom OpenAPI schema, uvicorn entrypoints

**OpenAPI:** Custom `openapi()` override in `main.py` sets `/health` security to `[]` (no auth required). All other routes inherit `APIKeyHeader` security scheme auto-generated from the `Security(APIKeyHeader)` dependency. Error response shapes declared via `responses=` on each route using `ErrorResponse` schema.

## Planned endpoints (not yet implemented)

- `POST /api/v1/library/scan` — trigger a Jellyfin library scan (`POST /Library/Media/Updated`)
- `POST /api/v1/library/paths` — add a local directory to a Jellyfin library
- `GET /api/v1/library/items` — search library contents (`GET /Items`)

These require a `library` router, `library` schemas, and expanded `services/jellyfin.py` coverage. Spec these against the actual Jellyfin instance's library configuration before implementing.

## Versioning

Version is derived from git tags via `hatch-vcs` - do not hardcode it anywhere. `src/medialab_jellyfin/_version.py` is generated at build time and is gitignored. To release a new version: merge to main, tag (`git tag -a vX.Y.Z -m "vX.Y.Z"`), push the tag (`git push origin vX.Y.Z`), create a GitHub Release from the tag, update `CHANGELOG.md` before tagging.

## Testing patterns

- Always use `uv run pytest`, never `python -m pytest`
- Always pytest style, never unittest
- `conftest.py` has two `autouse=True` fixtures: `patch_api_key` (mocks auth config) and `reset_rate_limiter` (clears limiter storage between tests)
- `client` fixture sends `X-API-Key` header by default; use `unauthed_client` fixture for auth rejection tests
- Mock `medialab_jellyfin.core.auth.config` (not `core.config`) when patching auth
- Mock `medialab_jellyfin.core.middleware.app_logger` when asserting on log output
