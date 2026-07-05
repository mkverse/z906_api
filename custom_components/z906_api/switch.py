import asyncio
import logging

from homeassistant.components.switch import SwitchEntity
from homeassistant.const import CONF_HOST

from .base_entity import Z906Entity
from .const import DOMAIN, Endpoints

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(hass, entry, async_add_entities):
    """Set up switches from config entry."""
    host = entry.data[CONF_HOST]
    coordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([
        Z906PowerSwitch(coordinator, host),
        Z906MuteSwitch(coordinator, host)
    ])

class Z906PowerSwitch(Z906Entity, SwitchEntity):
    """Power control switch."""

    _attr_name = "Power"
    _attr_translation_key = "power"

    def __init__(self, coordinator, host):
        super().__init__(coordinator, host)
        self._attr_unique_id = f"{self._host}-power"

    @property
    def available(self) -> bool:
        return (
            super().available
            and self.coordinator.data.get(Endpoints.POWER_STATE) is not None
        )

    @property
    def is_on(self):
        value = self.coordinator.data.get(Endpoints.POWER_STATE)
        return bool(value) if value is not None else None

    async def async_turn_on(self, **kwargs):
        power, _input, _mute = await asyncio.gather(
            self.async_send_command(Endpoints.POWER_ON),
            self.async_send_command(Endpoints.INPUT_ENABLE),
            self.async_send_command(Endpoints.MUTE_OFF)
        )

        if power is None:
            _LOGGER.warning("Power-on request failed; not updating switch state")
            return

        await self.coordinator.async_request_refresh()

    async def async_turn_off(self, **kwargs):
        result = await self.async_send_command(Endpoints.POWER_OFF)
        if result is None:
            _LOGGER.warning("Power-off request failed; not updating switch state")
            return

        await self.coordinator.async_request_refresh()


class Z906MuteSwitch(Z906Entity, SwitchEntity):
    """Mute control switch."""

    _attr_name = "Mute"
    _attr_translation_key = "mute"
    _attr_assumed_state = True

    def __init__(self, coordinator, host):
        super().__init__(coordinator, host)
        self._attr_unique_id = f"{self._host}-mute"
        self._attr_is_on = None

    @property
    def available(self) -> bool:
        """Mute has no read endpoint; only require the coordinator to be alive."""
        return super().available

    async def async_turn_on(self, **kwargs):
        result = await self.async_send_command(Endpoints.MUTE_ON)
        if result is None:
            _LOGGER.warning("Mute-on request failed; not updating switch state")
            return

        self._attr_is_on = True
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs):
        result = await self.async_send_command(Endpoints.MUTE_OFF)
        if result is None:
            _LOGGER.warning("Mute-off request failed; not updating switch state")
            return

        self._attr_is_on = False
        self.async_write_ha_state()
