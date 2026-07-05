import asyncio
import logging
import aiohttp
import async_timeout

from homeassistant.helpers.aiohttp_client import async_get_clientsession
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

class BaseZ906Entity:
    """Base entity providing common REST behavior."""

    def __init__(self, hass, host: str):
        self.hass = hass
        self._host = host
        self._session = async_get_clientsession(hass)
        self._attr_has_entity_name = True

    @property
    def device_info(self):
        return {
            "identifiers": {(DOMAIN, self._host)},
            "name": "Logitech Z906",
            "manufacturer": "Logitech",
            "model": "Z906 Sound System",
        }

    async def _send_request(self, endpoint: str, params=None):
        """Send a REST GET request to the API with error handling."""
        params = params or []
        url = f"http://{self._host}{endpoint}"
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

    async def _poll_value(self, endpoint: str):
        """GET endpoint and return data['value'], or None if unavailable.

        Marks the entity available/unavailable as a side effect so callers
        don't need to repeat the availability dance in every async_update.
        """
        data = await self._send_request(endpoint)
        if not data or "value" not in data:
            self._attr_available = False
            return None

        self._attr_available = True
        return data["value"]