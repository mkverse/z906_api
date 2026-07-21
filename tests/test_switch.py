"""Tests for the switch platform's spec table and generic entity."""

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from custom_components.z906_api.const import Endpoints
from custom_components.z906_api.switch import SWITCH_ENTITIES, Z906Switch


@pytest.fixture
def coordinator():
    return SimpleNamespace(
        data={},
        last_update_success=True,
        async_send=AsyncMock(return_value={"value": 1}),
        async_request_refresh=AsyncMock(),
    )


def _spec(suffix):
    return next(s for s in SWITCH_ENTITIES if s.unique_id_suffix == suffix)


def test_power_on_fires_three_commands_concurrently():
    commands = _spec("power").on()
    assert commands == [
        (Endpoints.POWER_ON, []),
        (Endpoints.INPUT_ENABLE, []),
        (Endpoints.MUTE_OFF, []),
    ]


def test_power_off_fires_one_command():
    assert _spec("power").off() == [(Endpoints.POWER_OFF, [])]


def test_mute_is_optimistic_with_no_read_endpoint():
    spec = _spec("mute")
    assert spec.optimistic is True
    assert spec.get_endpoint is None
    assert spec.on() == [(Endpoints.MUTE_ON, [])]
    assert spec.off() == [(Endpoints.MUTE_OFF, [])]


def test_power_switch_is_on_reads_from_coordinator(coordinator):
    coordinator.data = {Endpoints.POWER_STATE: 1}
    entity = Z906Switch(coordinator, "192.0.2.1", _spec("power"))
    assert entity.is_on is True
    assert entity.available is True


def test_mute_switch_is_on_starts_none_and_is_assumed_state(coordinator):
    entity = Z906Switch(coordinator, "192.0.2.1", _spec("mute"))
    assert entity.is_on is None
    assert entity._attr_assumed_state is True
    assert entity.available is True  # no read endpoint required


async def test_mute_turn_on_writes_optimistic_state(coordinator):
    entity = Z906Switch(coordinator, "192.0.2.1", _spec("mute"))
    entity.async_write_ha_state = lambda: None
    await entity.async_turn_on()
    assert entity.is_on is True
    coordinator.async_send.assert_awaited_once_with(Endpoints.MUTE_ON, [])
    coordinator.async_request_refresh.assert_not_awaited()


async def test_power_turn_on_requests_refresh_on_success(coordinator):
    entity = Z906Switch(coordinator, "192.0.2.1", _spec("power"))
    await entity.async_turn_on()
    assert coordinator.async_send.await_count == 3
    coordinator.async_request_refresh.assert_awaited_once()


async def test_power_turn_on_skips_refresh_if_any_of_three_fails(coordinator):
    coordinator.async_send = AsyncMock(side_effect=[{"value": 1}, None, {"value": 1}])
    entity = Z906Switch(coordinator, "192.0.2.1", _spec("power"))
    await entity.async_turn_on()
    coordinator.async_request_refresh.assert_not_awaited()
