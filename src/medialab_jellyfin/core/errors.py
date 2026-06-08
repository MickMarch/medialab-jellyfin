"""Application error codes and base exception for structured error responses."""

from enum import Enum


class ErrorCode(str, Enum):
    JELLYFIN_UNAVAILABLE = "JELLYFIN_UNAVAILABLE"
    PATH_NOT_FOUND = "PATH_NOT_FOUND"
    PERMISSION_DENIED = "PERMISSION_DENIED"
    INVALID_INPUT = "INVALID_INPUT"
    INTERNAL_ERROR = "INTERNAL_ERROR"
    UNAUTHORIZED = "UNAUTHORIZED"
    RATE_LIMITED = "RATE_LIMITED"


class AppException(Exception):
    def __init__(self, status_code: int, code: ErrorCode, detail: str) -> None:
        self.status_code = status_code
        self.code = code
        self.detail = detail
