import logging

from homeassistant.components.select import SelectEntity
from homeassistant.const import CONF_HOST

from .base_entity import Z906Entity
from .const import DOMAIN, Endpoints

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
    coordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([Z906InputSelect(coordinator, host)])


class Z906InputSelect(Z906Entity, SelectEntity):
    """Input selector for the Logitech Z906."""

    _attr_name = "Input Source"
    _attr_translation_key = "input"
    _attr_options = list(INPUT_OPTIONS.keys())

    def __init__(self, coordinator, host):
        super().__init__(coordinator, host)
        self._attr_unique_id = f"{self._host}-input"

    @property
    def available(self) -> bool:
        return (
            super().available
            and self.coordinator.data.get(Endpoints.INPUT_STATE) is not None
        )

    @property
    def current_option(self):
        value = self.coordinator.data.get(Endpoints.INPUT_STATE)
        if value is None:
            return None

        number = int(value)
        for name, val in INPUT_OPTIONS.items():
            if val == number:
                return name

        return None

    async def async_select_option(self, option: str):
        """Change the active input."""
        value = INPUT_OPTIONS.get(option)
        if value is None:
            _LOGGER.warning("Unknown input option: %s", option)
            return

        result = await self.async_send_command(f"{Endpoints.INPUT_SET}/{value}")
        if result is None:
            _LOGGER.warning("Input-select request failed; not updating state")
            return

        await self.coordinator.async_request_refresh()
