"""Select platform: input source, driven by a declarative spec table."""

import logging
from dataclasses import dataclass
from typing import Callable

from homeassistant.components.select import SelectEntity
from homeassistant.const import CONF_HOST

from .base_entity import Command, EntitySpec, Z906Entity
from .const import DOMAIN, Endpoints

_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True)
class SelectSpec(EntitySpec):
    """A named-option entity backed by an integer endpoint."""

    options: dict[str, int]
    write: Callable[[int], list[Command]]


def _set_input(value: int) -> list[Command]:
    return [(f"{Endpoints.INPUT_STATE}/{value}", [])]


SELECT_ENTITIES = [
    SelectSpec(
        name="Input Source",
        unique_id_suffix="input",
        get_endpoint=Endpoints.INPUT_STATE,
        cast=int,
        options={
            "TRS 5.1": 1,
            "RCA 2.0": 2,
            "Optical 1": 3,
            "Optical 2": 4,
            "Coaxial": 5,
        },
        write=_set_input,
    ),
]


async def async_setup_entry(hass, entry, async_add_entities):
    """Set up the input selector."""
    host = entry.data[CONF_HOST]
    coordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([Z906Select(coordinator, host, spec) for spec in SELECT_ENTITIES])


class Z906Select(Z906Entity, SelectEntity):
    """The input selector for the Logitech Z906, driven by SelectSpec."""

    def __init__(self, coordinator, host, spec: SelectSpec):
        super().__init__(coordinator, host, spec)
        self._spec: SelectSpec = spec
        self._attr_options = list(spec.options.keys())

    @property
    def current_option(self):
        number = self._read()
        if number is None:
            return None

        for name, val in self._spec.options.items():
            if val == number:
                return name

        return None

    async def async_select_option(self, option: str):
        """Change the active input."""
        value = self._spec.options.get(option)
        if value is None:
            _LOGGER.warning("Unknown input option: %s", option)
            return

        await self._send_and_settle(self._spec.write(value))
