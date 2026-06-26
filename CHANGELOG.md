# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- Project scaffolding: FastAPI app factory, structured error responses, static API key authentication, per-IP rate limiting, request logging middleware with `X-Request-ID` header, and `/api/v1/health` endpoint reporting Jellyfin reachability.
- Dockerfile with non-root user and two-stage uv install for minimal image size.
- GitHub Actions CI running pytest on push to main and PRs targeting main.
- VCS-based versioning via `hatch-vcs` - version derived from git tags.
- Ruff lint + format configuration enforcing the workspace rule set
  (`E,F,I,UP,B,SIM,PLR2004`, magic-value ban via `PLR2004`).
- Mypy static type checking with the pydantic plugin; the router `responses=`
  dict typing is relaxed per-module (annotation accuracy, not a behavior bug).
- Pre-commit hooks (ruff, whitespace, eof, yaml/toml checks).
- Dependabot config for `uv` and GitHub Actions updates.
- CI expanded from tests-only to ruff lint, format check, mypy, tests, and a
  project-dependency audit.
- `integration` pytest marker for tests needing real secrets or a live service.

### Changed

- Bumped `starlette` (>=1.3.1) and `pydantic-settings` (>=2.14.2) to clear CVEs
  surfaced by the new dependency audit.
