"""Tests for the sensor platform's spec table and generic entity."""

from types import SimpleNamespace

import pytest

from custom_components.z906_api.const import Endpoints
from custom_components.z906_api.sensor import SENSOR_ENTITIES, Z906Sensor


@pytest.fixture
def coordinator():
    return SimpleNamespace(data={}, last_update_success=True)


def test_temperature_native_value_casts_to_float(coordinator):
    coordinator.data = {Endpoints.TEMPERATURE: "21"}
    entity = Z906Sensor(coordinator, "192.0.2.1", SENSOR_ENTITIES[0])
    assert entity.native_value == 21.0


def test_temperature_disabled_by_default(coordinator):
    entity = Z906Sensor(coordinator, "192.0.2.1", SENSOR_ENTITIES[0])
    assert entity.entity_registry_enabled_default is False
