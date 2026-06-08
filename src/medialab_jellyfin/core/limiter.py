"""Rate limiter instance shared across the application."""

from slowapi import Limiter
from slowapi.util import get_remote_address

RATE_LIMIT_DEFAULT = "60/minute"

limiter = Limiter(key_func=get_remote_address)
