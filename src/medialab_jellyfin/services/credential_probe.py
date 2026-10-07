"""The slow credential probe: one authenticated read-only Jellyfin call on an interval.

Refusals on live calls already flip the key to invalid the moment they happen;
the probe exists for a key that expires while no job is running.
"""

import asyncio
from collections.abc import Awaitable, Callable

from medialab_jellyfin.core.config import config
from medialab_jellyfin.core.logger import app_logger
from medialab_jellyfin.services.jellyfin import probe_api_key

STARTUP_DELAY_SECONDS = 15.0


async def run_probe_loop(
    stop: asyncio.Event,
    *,
    sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
    startup_delay: float = STARTUP_DELAY_SECONDS,
) -> None:
    """Probe after a short startup delay, then every `credential_check_interval_seconds`."""
    await sleep(startup_delay)
    while not stop.is_set():
        try:
            await asyncio.to_thread(probe_api_key)
        except Exception:  # noqa: BLE001 - the loop must survive any single probe failure
            app_logger.exception("Credential probe failed")
        await sleep(float(config.credential_check_interval_seconds))
