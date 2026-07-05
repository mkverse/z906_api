from custom_components.z906_api.base_entity import BaseZ906Entity
from custom_components.z906_api.const import Endpoints
from homeassistant.components.sensor import SensorEntity, SensorDeviceClass
from homeassistant.const import CONF_HOST

async def async_setup_entry(hass, entry, async_add_entities):
    """Set up switches from config entry."""
    host = entry.data[CONF_HOST]
    async_add_entities([
        Z906TemperatureSensor(hass, host),
    ], True)

class Z906TemperatureSensor(BaseZ906Entity, SensorEntity):
    """Temperature sensor entity for the Logitech Z906 controller."""

    _attr_name = "Temperature"
    _attr_native_unit_of_measurement = "°C"
    _attr_device_class = SensorDeviceClass.TEMPERATURE
    _attr_translation_key = "temperature"

    def __init__(self, hass, host):
        super().__init__(hass, host)
        self._attr_unique_id = f"{self._host}-temperature"
        self._attr_native_value = None

    @property
    def entity_registry_enabled_default(self) -> bool:
        """Return if the entity should be enabled when first added to the entity registry."""
        return False

    @property
    def should_poll(self):
        """Poll periodically to fetch current temperature."""
        return True

    async def async_update(self):
        """Fetch the latest temperature from /temperature endpoint."""
        value = await self._poll_value(Endpoints.TEMPERATURE)
        if value is not None:
            self._attr_native_value = float(value)