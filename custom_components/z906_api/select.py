import logging

from homeassistant.components.select import SelectEntity
from homeassistant.const import CONF_HOST
from custom_components.z906_api.base_entity import BaseZ906Entity
from custom_components.z906_api.const import Endpoints

_LOGGER = logging.getLogger(__name__)

INPUT_OPTIONS = {
    "TRS 5.1": 1,
    "RCA 2.0": 2,
    "Optical 1": 3,
    "Optical 2": 4,
    "Coaxial": 5,
}

async def async_setup_entry(hass, entry, async_add_entities):
    """Set up the input selector."""
    host = entry.data[CONF_HOST]
    async_add_entities([Z906InputSelect(hass, host)], True)


class Z906InputSelect(BaseZ906Entity, SelectEntity):
    """Input selector for the Logitech Z906."""

    _attr_name = "Input Source"
    _attr_translation_key = "input"
    _attr_options = list(INPUT_OPTIONS.keys())

    def __init__(self, hass, host):
        super().__init__(hass, host)
        self._attr_unique_id = f"{self._host}-input"
        self._attr_current_option = None

    @property
    def should_poll(self):
        """Poll the device for input state."""
        return True

    async def async_select_option(self, option: str):
        """Change the active input."""
        value = INPUT_OPTIONS.get(option)
        if value is None:
            _LOGGER.warning("Unknown input option: %s", option)
            return

        result = await self._send_request(f"{Endpoints.INPUT_SET}/{value}")
        if result is None:
            _LOGGER.warning("Input-select request failed; not updating state")
            return

        self._attr_current_option = option
        self.async_write_ha_state()

    async def async_update(self):
        """Poll the device for the currently active input."""
        value = await self._poll_value(Endpoints.INPUT_STATE)
        if value is None:
            return

        number = int(value)
        for name, val in INPUT_OPTIONS.items():
            if val == number:
                self._attr_current_option = name
                break