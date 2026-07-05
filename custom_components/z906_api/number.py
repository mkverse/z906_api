import logging

from custom_components.z906_api.base_entity import BaseZ906Entity
from custom_components.z906_api.const import Endpoints
from homeassistant.components.number import NumberEntity
from homeassistant.const import CONF_HOST

_LOGGER = logging.getLogger(__name__)

VOLUME_ENTITIES = [
    # (name, unique_id_suffix, get_endpoint, set_endpoint)
    ("Main Volume", "main-volume", Endpoints.VOLUME_MAIN, Endpoints.VOLUME_MAIN_SET),
    ("Subwoofer Volume", "subwoofer-volume", Endpoints.VOLUME_SUBWOOFER, Endpoints.VOLUME_SUBWOOFER_SET),
    ("Center Volume", "center-volume", Endpoints.VOLUME_CENTER, Endpoints.VOLUME_CENTER_SET),
    ("Rear Volume", "rear-volume", Endpoints.VOLUME_REAR, Endpoints.VOLUME_REAR_SET),
]

async def async_setup_entry(hass, entry, async_add_entities):
    """Set up volume sliders from config entry."""
    host = entry.data[CONF_HOST]
    async_add_entities(
        [
            Z906Volume(hass, host, name, unique_id_suffix, get_endpoint, set_endpoint)
            for name, unique_id_suffix, get_endpoint, set_endpoint in VOLUME_ENTITIES
        ],
        True,
    )

class Z906Volume(BaseZ906Entity, NumberEntity):
    """A volume slider (main/subwoofer/center/rear) for the Logitech Z906."""

    _attr_native_min_value = 0
    _attr_native_max_value = 255
    _attr_native_step = 1
    _attr_mode = "slider"

    def __init__(self, hass, host, name, unique_id_suffix, get_endpoint, set_endpoint):
        super().__init__(hass, host)
        self._attr_name = name
        self._attr_unique_id = f"{self._host}-{unique_id_suffix}"
        self._attr_native_value = 0
        self._get_endpoint = get_endpoint
        self._set_endpoint = set_endpoint

    @property
    def should_poll(self):
        """Poll the device to keep the current volume level updated."""
        return True

    @property
    def icon(self) -> str | None:
        """Icon of the entity."""
        if self._attr_native_value < 85:
            return "mdi:volume-low"
        elif self._attr_native_value < 170:
            return "mdi:volume-medium"
        else:
            return "mdi:volume-high"

    async def async_set_native_value(self, value: float):
        """Handle user changing the volume slider."""
        result = await self._send_request(self._set_endpoint, [("value", int(value))])
        if result is None:
            _LOGGER.warning("Volume-set request failed for %s; not updating state", self._attr_name)
            return

        self._attr_native_value = value
        self.async_write_ha_state()

    async def async_update(self):
        """Poll the current volume level from the device."""
        value = await self._poll_value(self._get_endpoint)
        if value is not None:
            self._attr_native_value = int(value)
