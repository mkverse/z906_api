"""Tests for the select platform's spec table and generic entity."""

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from custom_components.z906_api.const import Endpoints
from custom_components.z906_api.select import SELECT_ENTITIES, Z906Select


@pytest.fixture
def coordinator():
    return SimpleNamespace(
        data={},
        last_update_success=True,
        async_send=AsyncMock(return_value={"value": 1}),
        async_request_refresh=AsyncMock(),
    )


def _spec():
    return SELECT_ENTITIES[0]


def test_write_builds_path_with_value_appended():
    assert _spec().write(3) == [("/input/3", [])]


def test_current_option_reverse_looks_up_the_name(coordinator):
    coordinator.data = {Endpoints.INPUT_STATE: 3}
    entity = Z906Select(coordinator, "192.0.2.1", _spec())
    assert entity.current_option == "Optical 1"


def test_current_option_none_for_unknown_number(coordinator):
    coordinator.data = {Endpoints.INPUT_STATE: 99}
    entity = Z906Select(coordinator, "192.0.2.1", _spec())
    assert entity.current_option is None


async def test_select_option_sends_command_and_refreshes(coordinator):
    entity = Z906Select(coordinator, "192.0.2.1", _spec())
    await entity.async_select_option("Coaxial")
    coordinator.async_send.assert_awaited_once_with("/input/5", [])
    coordinator.async_request_refresh.assert_awaited_once()


async def test_select_unknown_option_warns_and_sends_nothing(coordinator, caplog):
    entity = Z906Select(coordinator, "192.0.2.1", _spec())
    await entity.async_select_option("Not A Real Input")
    coordinator.async_send.assert_not_awaited()
    assert "Unknown input option" in caplog.text
