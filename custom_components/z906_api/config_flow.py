import voluptuous as vol
import aiohttp

from homeassistant import config_entries
from homeassistant.const import CONF_HOST
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from custom_components.z906_api.const import DOMAIN, Endpoints

class Z906ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle config flow for Logitech Z906 API."""

    async def async_step_user(self, user_input=None):
        errors = {}

        if user_input is not None:
            host = user_input[CONF_HOST]
            url = f"http://{host}{Endpoints.POWER_STATE}"
            session = async_get_clientsession(self.hass)
            try:
                async with session.get(url, timeout=5) as resp:
                    if resp.status != 200:
                        errors["base"] = "cannot_connect"
                    else:
                        data = await resp.json(content_type=None)
                        if not data or "value" not in data:
                            errors["base"] = "cannot_connect"
            except Exception:
                errors["base"] = "cannot_connect"

            if not errors:
                return self.async_create_entry(title=f"Z906 ({host})", data=user_input)

        schema = vol.Schema({vol.Required(CONF_HOST): str})
        return self.async_show_form(step_id="user", data_schema=schema, errors=errors)