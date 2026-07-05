import asyncio
import logging

import aiohttp
import async_timeout
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_HOST
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import DOMAIN, Endpoints

_LOGGER = logging.getLogger(__name__)

STEP_USER_SCHEMA = vol.Schema({vol.Required(CONF_HOST): str})


async def _validate_host(hass, host: str) -> bool:
    """Probe /power on the bridge, mirroring the coordinator's request shape."""
    url = f"http://{host}{Endpoints.POWER_STATE}"
    session = async_get_clientsession(hass)
    try:
        async with async_timeout.timeout(5):
            async with session.get(url) as resp:
                if resp.status != 200:
                    return False
                data = await resp.json(content_type=None)
                return bool(data) and "value" in data
    except asyncio.TimeoutError:
        return False
    except aiohttp.ClientError:
        return False
    except Exception:
        _LOGGER.exception("Unexpected error validating host %s", host)
        return False


class Z906ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle config flow for Logitech Z906 API."""

    async def async_step_user(self, user_input=None):
        errors = {}

        if user_input is not None:
            host = user_input[CONF_HOST]

            await self.async_set_unique_id(host)
            self._abort_if_unique_id_configured()

            if await _validate_host(self.hass, host):
                return self.async_create_entry(title=f"Z906 ({host})", data=user_input)

            errors["base"] = "cannot_connect"

        return self.async_show_form(step_id="user", data_schema=STEP_USER_SCHEMA, errors=errors)

    async def async_step_reconfigure(self, user_input=None):
        """Allow changing the host of an existing entry."""
        errors = {}
        entry = self._get_reconfigure_entry()

        if user_input is not None:
            host = user_input[CONF_HOST]

            await self.async_set_unique_id(host)
            self._abort_if_unique_id_mismatch()

            if await _validate_host(self.hass, host):
                return self.async_update_reload_and_abort(entry, data=user_input)

            errors["base"] = "cannot_connect"

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=self.add_suggested_values_to_schema(
                STEP_USER_SCHEMA, user_input or entry.data
            ),
            errors=errors,
        )
