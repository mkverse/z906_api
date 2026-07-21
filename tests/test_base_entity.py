"""Tests for the shared Z906Entity read/available/write contract."""

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from custom_components.z906_api.base_entity import EntitySpec, Z906Entity
from custom_components.z906_api.const import Endpoints


@pytest.fixture
def coordinator():
    """A fake coordinator: just the surface Z906Entity actually depends on."""
    return SimpleNamespace(
        data={},
        last_update_success=True,
        async_send=AsyncMock(return_value={"value": 1}),
        async_request_refresh=AsyncMock(),
    )


def _entity(coordinator, get_endpoint=Endpoints.POWER_STATE, cast=bool):
    spec = EntitySpec(
        name="Test Entity",
        unique_id_suffix="test",
        get_endpoint=get_endpoint,
        cast=cast,
    )
    return Z906Entity(coordinator, "192.0.2.1", spec)


def test_available_true_when_endpoint_has_data(coordinator):
    coordinator.data = {Endpoints.POWER_STATE: 1}
    entity = _entity(coordinator)
    assert entity.available is True


def test_available_false_when_endpoint_missing(coordinator):
    coordinator.data = {Endpoints.POWER_STATE: None}
    entity = _entity(coordinator)
    assert entity.available is False


def test_available_true_without_read_endpoint(coordinator):
    coordinator.data = {}
    entity = _entity(coordinator, get_endpoint=None)
    assert entity.available is True


def test_read_casts_the_endpoint_value(coordinator):
    coordinator.data = {Endpoints.POWER_STATE: 1}
    entity = _entity(coordinator, cast=bool)
    assert entity._read() is True


def test_read_returns_none_when_endpoint_missing(coordinator):
    coordinator.data = {Endpoints.POWER_STATE: None}
    entity = _entity(coordinator)
    assert entity._read() is None


async def test_send_and_settle_refreshes_on_success(coordinator):
    entity = _entity(coordinator)
    await entity._send_and_settle([(Endpoints.POWER_ON, [])])
    coordinator.async_send.assert_awaited_once_with(Endpoints.POWER_ON, [])
    coordinator.async_request_refresh.assert_awaited_once()


async def test_send_and_settle_warns_and_skips_refresh_on_any_failure(coordinator, caplog):
    coordinator.async_send = AsyncMock(side_effect=[{"value": 1}, None])
    entity = _entity(coordinator)
    await entity._send_and_settle(
        [(Endpoints.POWER_ON, []), (Endpoints.INPUT_ENABLE, [])]
    )
    coordinator.async_request_refresh.assert_not_awaited()
    assert "command failed" in caplog.text


async def test_send_and_settle_writes_optimistic_value_on_success(coordinator):
    entity = _entity(coordinator)
    entity.async_write_ha_state = lambda: None
    await entity._send_and_settle([(Endpoints.MUTE_ON, [])], optimistic_value=True)
    assert entity._attr_is_on is True
    coordinator.async_request_refresh.assert_not_awaited()
