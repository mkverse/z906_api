from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.const import CONF_HOST

from .base_entity import Z906Entity
from .const import DOMAIN, Endpoints

async def async_setup_entry(hass, entry, async_add_entities):
    """Set up sensors from config entry."""
    host = entry.data[CONF_HOST]
    coordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([
        Z906TemperatureSensor(coordinator, host),
    ])

class Z906TemperatureSensor(Z906Entity, SensorEntity):
    """Temperature sensor entity for the Logitech Z906 controller."""

    _attr_name = "Temperature"
    _attr_native_unit_of_measurement = "°C"
    _attr_device_class = SensorDeviceClass.TEMPERATURE
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_translation_key = "temperature"
    _attr_entity_registry_enabled_default = False

    def __init__(self, coordinator, host):
        super().__init__(coordinator, host)
        self._attr_unique_id = f"{self._host}-temperature"

    @property
    def available(self) -> bool:
        return (
            super().available
            and self.coordinator.data.get(Endpoints.TEMPERATURE) is not None
        )

    @property
    def native_value(self):
        value = self.coordinator.data.get(Endpoints.TEMPERATURE)
        return float(value) if value is not None else None
