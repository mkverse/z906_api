"""Data update coordinator for the Logitech Z906 integration.

Centralizes all REST I/O to the bridge: a single poll cycle fetches every
readable value concurrently, and commands are sent through the same
choke point so there's one place that owns the aiohttp session, timeout,
and error handling.
"""

import asyncio
import logging
from datetime import timedelta
from typing import Any

import aiohttp
import async_timeout

from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import DOMAIN, Endpoints

_LOGGER = logging.getLogger(__name__)

UPDATE_INTERVAL = timedelta(seconds=30)

# Read endpoints polled every update cycle, keyed by the Endpoints value
# that entities look up their state by.
POLLED_ENDPOINTS = [
    Endpoints.POWER_STATE,
    Endpoints.INPUT_STATE,
    Endpoints.VOLUME_MAIN,
    Endpoints.VOLUME_CENTER,
    Endpoints.VOLUME_REAR,
    Endpoints.VOLUME_SUBWOOFER,
    Endpoints.TEMPERATURE,
]


class Z906Coordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Fetches all Z906 bridge state on a single schedule."""

    def __init__(self, hass: HomeAssistant, host: str) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=UPDATE_INTERVAL,
        )
        self.host = host
        self._session = async_get_clientsession(hass)

    async def async_send(self, endpoint: str, params=None):
        """Send a REST GET request to the bridge with error handling.

        Used for both polling and commands, so it stays the single I/O
        choke point. Returns the parsed JSON body, or None on any error.
        """
        params = params or []
        url = f"http://{self.host}{endpoint}"
        try:
            async with async_timeout.timeout(8):
                async with self._session.get(url, params=params) as response:
                    if response.status != 200:
                        _LOGGER.warning("Unexpected status %s from %s", response.status, url)
                        return None

                    try:
                        return await response.json(content_type=None)
                    except Exception:
                        _LOGGER.error("Invalid JSON response from %s", url)
                        return None
        except asyncio.TimeoutError:
            _LOGGER.error("Timeout while calling %s", url)
        except aiohttp.ClientError as e:
            _LOGGER.error("Network error while calling %s: %s", url, e)
        except Exception as e:
            _LOGGER.exception("Unhandled exception calling %s: %s", url, e)

        return None

    async def _async_update_data(self) -> dict[str, Any]:
        """Poll every read endpoint concurrently and return value-by-endpoint."""
        results = await asyncio.gather(
            *(self.async_send(endpoint) for endpoint in POLLED_ENDPOINTS)
        )

        data: dict[str, Any] = {}
        for endpoint, result in zip(POLLED_ENDPOINTS, results):
            data[endpoint] = result["value"] if result and "value" in result else None

        return data
