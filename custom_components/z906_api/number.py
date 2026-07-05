import logging

from homeassistant.components.number import NumberEntity
from homeassistant.const import CONF_HOST

from .base_entity import Z906Entity
from .const import DOMAIN, Endpoints

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
    coordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        [
            Z906Volume(coordinator, host, name, unique_id_suffix, get_endpoint, set_endpoint)
            for name, unique_id_suffix, get_endpoint, set_endpoint in VOLUME_ENTITIES
        ]
    )

class Z906Volume(Z906Entity, NumberEntity):
    """A volume slider (main/subwoofer/center/rear) for the Logitech Z906."""

    _attr_native_min_value = 0
    _attr_native_max_value = 255
    _attr_native_step = 1
    _attr_mode = "slider"

    def __init__(self, coordinator, host, name, unique_id_suffix, get_endpoint, set_endpoint):
        super().__init__(coordinator, host)
        self._attr_name = name
        self._attr_unique_id = f"{self._host}-{unique_id_suffix}"
        self._get_endpoint = get_endpoint
        self._set_endpoint = set_endpoint

    @property
    def available(self) -> bool:
        return (
            super().available
            and self.coordinator.data.get(self._get_endpoint) is not None
        )

    @property
    def native_value(self):
        value = self.coordinator.data.get(self._get_endpoint)
        return int(value) if value is not None else None

    @property
    def icon(self) -> str | None:
        """Icon of the entity."""
        value = self.native_value or 0
        if value < 85:
            return "mdi:volume-low"
        elif value < 170:
            return "mdi:volume-medium"
        else:
            return "mdi:volume-high"

    async def async_set_native_value(self, value: float):
        """Handle user changing the volume slider."""
        result = await self.async_send_command(self._set_endpoint, [("value", int(value))])
        if result is None:
            _LOGGER.warning("Volume-set request failed for %s; not updating state", self._attr_name)
            return

        await self.coordinator.async_request_refresh()
