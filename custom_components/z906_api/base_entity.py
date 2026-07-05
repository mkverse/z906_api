from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import Z906Coordinator


class Z906Entity(CoordinatorEntity[Z906Coordinator]):
    """Base entity providing shared device info and command dispatch."""

    def __init__(self, coordinator: Z906Coordinator, host: str):
        super().__init__(coordinator)
        self._host = host
        self._attr_has_entity_name = True

    @property
    def device_info(self):
        return {
            "identifiers": {(DOMAIN, self._host)},
            "name": "Logitech Z906",
            "manufacturer": "Logitech",
            "model": "Z906 Sound System",
        }

    async def async_send_command(self, endpoint: str, params=None):
        """Send a command to the bridge via the coordinator's shared session."""
        return await self.coordinator.async_send(endpoint, params)
