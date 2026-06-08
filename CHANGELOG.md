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
