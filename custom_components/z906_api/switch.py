"""Switch platform: power and mute, driven by a declarative spec table."""

import logging
from dataclasses import dataclass
from typing import Callable

from homeassistant.components.switch import SwitchEntity
from homeassistant.const import CONF_HOST

from .base_entity import Command, EntitySpec, Z906Entity
from .const import DOMAIN, Endpoints

_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True)
class SwitchSpec(EntitySpec):
    """A toggleable entity: on/off command-builders, optionally optimistic."""

    on: Callable[[], list[Command]]
    off: Callable[[], list[Command]]
    optimistic: bool = False


SWITCH_ENTITIES = [
    SwitchSpec(
        name="Power",
        unique_id_suffix="power",
        get_endpoint=Endpoints.POWER_STATE,
        cast=bool,
        on=lambda: [
            (Endpoints.POWER_ON, []),
            (Endpoints.INPUT_ENABLE, []),
            (Endpoints.MUTE_OFF, []),
        ],
        off=lambda: [(Endpoints.POWER_OFF, [])],
    ),
    SwitchSpec(
        name="Mute",
        unique_id_suffix="mute",
        get_endpoint=None,
        cast=bool,
        on=lambda: [(Endpoints.MUTE_ON, [])],
        off=lambda: [(Endpoints.MUTE_OFF, [])],
        optimistic=True,
    ),
]


async def async_setup_entry(hass, entry, async_add_entities):
    """Set up switches from config entry."""
    host = entry.data[CONF_HOST]
    coordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([Z906Switch(coordinator, host, spec) for spec in SWITCH_ENTITIES])


class Z906Switch(Z906Entity, SwitchEntity):
    """A power/mute-style toggle for the Logitech Z906, driven by SwitchSpec."""

    def __init__(self, coordinator, host, spec: SwitchSpec):
        super().__init__(coordinator, host, spec)
        self._spec: SwitchSpec = spec
        if spec.optimistic:
            self._attr_assumed_state = True
            self._attr_is_on = None

    @property
    def is_on(self):
        if self._spec.optimistic:
            return self._attr_is_on
        return self._read()

    async def async_turn_on(self, **kwargs):
        await self._send_and_settle(
            self._spec.on(), optimistic_value=True if self._spec.optimistic else None
        )

    async def async_turn_off(self, **kwargs):
        await self._send_and_settle(
            self._spec.off(), optimistic_value=False if self._spec.optimistic else None
        )
