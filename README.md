# Medialab Jellyfin

A FastAPI microservice that wraps the Jellyfin media server API. Exposes a REST API for triggering library scans and managing library paths — intended to be called by an external orchestrator (e.g. a Discord bot or workflow coordinator) that handles cross-service automation such as post-download library updates.

---

## Prerequisites

### Jellyfin

1. Install and run [Jellyfin](https://jellyfin.org/downloads).
2. Sign in to the Jellyfin dashboard and go to **Administration → API Keys**.
3. Generate an API key and copy it.
4. Note the host and port Jellyfin is running on (default: `8096`).

### Python

Requires Python 3.12+. Install [uv](https://github.com/astral-sh/uv) (recommended) or use pip.

---

## Setup

### 1. Clone and install dependencies

```bash
git clone <repo-url>
cd medialab-jellyfin
uv sync --dev
# or: pip install -e ".[dev]"
```

### 2. Configure environment variables

Copy the example env file and populate it:

```bash
cp .env.example .env
```

Edit `.env`:

```env
# Jellyfin
JELLYFIN_HOST=127.0.0.1
JELLYFIN_PORT=8096
JELLYFIN_API_KEY=your_jellyfin_api_key

# API authentication
API_KEY=your_api_key

# Optional — defaults shown
API_HOST=0.0.0.0
API_PORT=8001
```

### 3. Run

```bash
# Development (hot-reload)
uv run medialab-jellyfin-dev

# Production
uv run medialab-jellyfin
```

The API serves interactive documentation at `/docs` and the OpenAPI schema at `/openapi.json`.

---

## API Overview

- `GET /api/v1/health` — public, no auth. Reports uptime and Jellyfin reachability.

All other endpoints require an `X-API-Key` header matching the configured `API_KEY`.

Error responses follow the shape `{"status": "error", "code": "<ErrorCode>", "detail": "..."}`.

Rate limit: 60 requests/minute per client IP. Exceeding it returns `429` with a `Retry-After` header.

Every response includes an `X-Request-ID` UUID header for cross-service call correlation.

---

## Testing

```bash
uv run pytest
```

## Docker

```bash
docker build -t medialab-jellyfin --build-arg APP_VERSION=$(git describe --tags --always) .
docker run -p 8001:8001 --env-file .env medialab-jellyfin
```
