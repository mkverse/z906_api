"""Tests for the number platform's spec table and generic entity."""

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from custom_components.z906_api.const import Endpoints
from custom_components.z906_api.number import VOLUME_ENTITIES, Z906Number


@pytest.fixture
def coordinator():
    return SimpleNamespace(
        data={},
        last_update_success=True,
        async_send=AsyncMock(return_value={"value": 1}),
        async_request_refresh=AsyncMock(),
    )


def _spec(suffix):
    return next(s for s in VOLUME_ENTITIES if s.unique_id_suffix == suffix)


def test_main_volume_cast_converts_raw_to_percent():
    assert _spec("main-volume").cast(255) == 100
    assert _spec("main-volume").cast(0) == 0
    assert _spec("main-volume").cast(128) == 50


def test_main_volume_write_converts_percent_to_raw():
    assert _spec("main-volume").write(100) == [(Endpoints.VOLUME_MAIN_SET, [("value", 255)])]
    assert _spec("main-volume").write(0) == [(Endpoints.VOLUME_MAIN_SET, [("value", 0)])]


def test_all_four_volume_entities_present():
    suffixes = {s.unique_id_suffix for s in VOLUME_ENTITIES}
    assert suffixes == {"main-volume", "subwoofer-volume", "center-volume", "rear-volume"}


def test_native_value_reads_and_converts(coordinator):
    coordinator.data = {Endpoints.VOLUME_MAIN: 128}
    entity = Z906Number(coordinator, "192.0.2.1", _spec("main-volume"))
    assert entity.native_value == 50


def test_icon_reflects_volume_level(coordinator):
    coordinator.data = {Endpoints.VOLUME_MAIN: 0}
    entity = Z906Number(coordinator, "192.0.2.1", _spec("main-volume"))
    assert entity.icon == "mdi:volume-low"
    coordinator.data = {Endpoints.VOLUME_MAIN: 255}
    assert entity.icon == "mdi:volume-high"


async def test_set_native_value_sends_converted_command_and_refreshes(coordinator):
    entity = Z906Number(coordinator, "192.0.2.1", _spec("main-volume"))
    await entity.async_set_native_value(50)
    coordinator.async_send.assert_awaited_once_with(Endpoints.VOLUME_MAIN_SET, [("value", 128)])
    coordinator.async_request_refresh.assert_awaited_once()
