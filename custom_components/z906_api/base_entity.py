"""Shared entity base and declarative spec for all Z906 platforms."""

import asyncio
import logging
from dataclasses import dataclass
from typing import Any, Callable

from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, Endpoints
from .coordinator import Z906Coordinator

_LOGGER = logging.getLogger(__name__)

Command = tuple[str, list[tuple[str, Any]]]


@dataclass(frozen=True)
class EntitySpec:
    """Shared fields every Z906 entity declares about itself."""

    name: str
    unique_id_suffix: str
    get_endpoint: Endpoints | None
    cast: Callable[[Any], Any]


class Z906Entity(CoordinatorEntity[Z906Coordinator]):
    """Base entity: device info, and the shared read/available/write contract."""

    def __init__(self, coordinator: Z906Coordinator, host: str, spec: EntitySpec):
        super().__init__(coordinator)
        self._host = host
        self._spec = spec
        self._attr_has_entity_name = True
        self._attr_name = spec.name
        self._attr_unique_id = f"{host}-{spec.unique_id_suffix}"
        self._attr_translation_key = spec.unique_id_suffix

    @property
    def device_info(self):
        return {
            "identifiers": {(DOMAIN, self._host)},
            "name": "Logitech Z906",
            "manufacturer": "Logitech",
            "model": "Z906 Sound System",
        }

    @property
    def available(self) -> bool:
        """True if the coordinator is alive and (if declared) the read endpoint has data."""
        if not super().available:
            return False
        if self._spec.get_endpoint is None:
            return True
        return self.coordinator.data.get(self._spec.get_endpoint) is not None

    def _read(self):
        """Return the cast value at the spec's read endpoint, or None."""
        if self._spec.get_endpoint is None:
            return None
        value = self.coordinator.data.get(self._spec.get_endpoint)
        return self._spec.cast(value) if value is not None else None

    async def _send_and_settle(
        self, commands: list[Command], *, optimistic_value: bool | None = None
    ) -> None:
        """Send one or more commands concurrently and settle resulting state.

        Warns and leaves state untouched if any command fails. On success,
        either writes `optimistic_value` directly (for entities with no read
        endpoint) or requests a coordinator refresh so state is read back.
        """
        results = await asyncio.gather(
            *(self.async_send_command(endpoint, params) for endpoint, params in commands)
        )
        if any(result is None for result in results):
            _LOGGER.warning("%s command failed; not updating state", self._spec.name)
            return

        if optimistic_value is not None:
            self._attr_is_on = optimistic_value
            self.async_write_ha_state()
        else:
            await self.coordinator.async_request_refresh()

    async def async_send_command(self, endpoint: str, params=None):
        """Send a command to the bridge via the coordinator's shared session."""
        return await self.coordinator.async_send(endpoint, params)
