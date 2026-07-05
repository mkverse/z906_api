import asyncio
import logging

from custom_components.z906_api.base_entity import BaseZ906Entity
from custom_components.z906_api.const import Endpoints
from homeassistant.components.switch import SwitchEntity
from homeassistant.const import CONF_HOST

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(hass, entry, async_add_entities):
    """Set up switches from config entry."""
    host = entry.data[CONF_HOST]
    async_add_entities([
        Z906PowerSwitch(hass, host),
        Z906MuteSwitch(hass, host)
    ], True)

class Z906PowerSwitch(BaseZ906Entity, SwitchEntity):
    """Power control switch."""

    _attr_name = "Power"
    _attr_translation_key = "power"

    def __init__(self, hass, host):
        super().__init__(hass, host)
        self._attr_unique_id = f"{self._host}-power"

    @property
    def should_poll(self):
        """Power entity polls /power to track its state."""
        return True

    async def async_turn_on(self, **kwargs):
        power, _input, _mute = await asyncio.gather(
            self._send_request(Endpoints.POWER_ON),
            self._send_request(Endpoints.INPUT_ENABLE),
            self._send_request(Endpoints.MUTE_OFF)
        )

        if power is None:
            _LOGGER.warning("Power-on request failed; not updating switch state")
            return

        self._attr_is_on = True
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs):
        result = await self._send_request(Endpoints.POWER_OFF)
        if result is None:
            _LOGGER.warning("Power-off request failed; not updating switch state")
            return

        self._attr_is_on = False
        self.async_write_ha_state()

    async def async_update(self):
        """Poll the /power endpoint for current state."""
        value = await self._poll_value(Endpoints.POWER_STATE)
        if value is not None:
            self._attr_is_on = bool(value)


class Z906MuteSwitch(BaseZ906Entity, SwitchEntity):
    """Mute control switch."""

    _attr_name = "Mute"
    _attr_translation_key = "mute"

    def __init__(self, hass, host):
        super().__init__(hass, host)
        self._attr_unique_id = f"{self._host}-mute"

    @property
    def should_poll(self):
        """Mute entity doesn’t poll—state only changes via commands."""
        return False

    async def async_turn_on(self, **kwargs):
        result = await self._send_request(Endpoints.MUTE_ON)
        if result is None:
            _LOGGER.warning("Mute-on request failed; not updating switch state")
            return

        self._attr_is_on = True
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs):
        result = await self._send_request(Endpoints.MUTE_OFF)
        if result is None:
            _LOGGER.warning("Mute-off request failed; not updating switch state")
            return

        self._attr_is_on = False
        self.async_write_ha_state()