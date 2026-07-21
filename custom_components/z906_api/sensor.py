"""Sensor platform: read-only temperature, driven by a declarative spec table."""

from dataclasses import dataclass

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.const import CONF_HOST

from .base_entity import EntitySpec, Z906Entity
from .const import DOMAIN, Endpoints


@dataclass(frozen=True)
class SensorSpec(EntitySpec):
    """A read-only entity. No write side."""


SENSOR_ENTITIES = [
    SensorSpec(
        name="Temperature",
        unique_id_suffix="temperature",
        get_endpoint=Endpoints.TEMPERATURE,
        cast=float,
    ),
]


async def async_setup_entry(hass, entry, async_add_entities):
    """Set up sensors from config entry."""
    host = entry.data[CONF_HOST]
    coordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([Z906Sensor(coordinator, host, spec) for spec in SENSOR_ENTITIES])


class Z906Sensor(Z906Entity, SensorEntity):
    """A read-only sensor for the Logitech Z906, driven by SensorSpec."""

    _attr_native_unit_of_measurement = "°C"
    _attr_device_class = SensorDeviceClass.TEMPERATURE
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_entity_registry_enabled_default = False

    @property
    def native_value(self):
        return self._read()
