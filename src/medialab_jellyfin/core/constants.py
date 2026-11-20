"""Application-wide constants: OpenAPI tags and process start time for uptime tracking."""

import time

TAG_SYSTEM = "System"
TAG_LIBRARY = "Library"

API_START_TIME: float = time.time()
