"""Number platform: volume sliders, driven by a declarative spec table."""

from dataclasses import dataclass
from typing import Callable

from homeassistant.components.number import NumberEntity
from homeassistant.const import CONF_HOST, PERCENTAGE

from .base_entity import Command, EntitySpec, Z906Entity
from .const import DOMAIN, Endpoints

RAW_MAX_VALUE = 255


def _raw_to_percent(value: int) -> int:
    return round(value / RAW_MAX_VALUE * 100)


def _percent_to_raw(percent: float) -> int:
    return max(0, min(RAW_MAX_VALUE, round(percent / 100 * RAW_MAX_VALUE)))


@dataclass(frozen=True)
class NumberSpec(EntitySpec):
    """A 0-100% slider backed by a 0-255 raw endpoint."""

    write: Callable[[float], list[Command]]


def _volume_spec(
    name: str, unique_id_suffix: str, get_endpoint: Endpoints, set_endpoint: Endpoints
) -> NumberSpec:
    return NumberSpec(
        name=name,
        unique_id_suffix=unique_id_suffix,
        get_endpoint=get_endpoint,
        cast=lambda v: _raw_to_percent(int(v)),
        write=lambda value: [(set_endpoint, [("value", _percent_to_raw(value))])],
    )


VOLUME_ENTITIES = [
    _volume_spec("Main Volume", "main-volume", Endpoints.VOLUME_MAIN, Endpoints.VOLUME_MAIN_SET),
    _volume_spec(
        "Subwoofer Volume", "subwoofer-volume", Endpoints.VOLUME_SUBWOOFER, Endpoints.VOLUME_SUBWOOFER_SET
    ),
    _volume_spec("Center Volume", "center-volume", Endpoints.VOLUME_CENTER, Endpoints.VOLUME_CENTER_SET),
    _volume_spec("Rear Volume", "rear-volume", Endpoints.VOLUME_REAR, Endpoints.VOLUME_REAR_SET),
]


async def async_setup_entry(hass, entry, async_add_entities):
    """Set up volume sliders from config entry."""
    host = entry.data[CONF_HOST]
    coordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([Z906Number(coordinator, host, spec) for spec in VOLUME_ENTITIES])


class Z906Number(Z906Entity, NumberEntity):
    """A volume slider for the Logitech Z906, driven by NumberSpec."""

    _attr_native_min_value = 0
    _attr_native_max_value = 100
    _attr_native_step = 1
    _attr_native_unit_of_measurement = PERCENTAGE
    _attr_mode = "slider"

    def __init__(self, coordinator, host, spec: NumberSpec):
        super().__init__(coordinator, host, spec)
        self._spec: NumberSpec = spec

    @property
    def native_value(self):
        return self._read()

    @property
    def icon(self) -> str | None:
        """Icon of the entity."""
        value = self.native_value or 0
        if value < 34:
            return "mdi:volume-low"
        elif value < 67:
            return "mdi:volume-medium"
        else:
            return "mdi:volume-high"

    async def async_set_native_value(self, value: float):
        """Handle user changing the volume slider."""
        await self._send_and_settle(self._spec.write(value))
