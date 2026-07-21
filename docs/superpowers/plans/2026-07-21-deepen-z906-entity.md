# Deepen Z906Entity Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Collapse the duplicated `available`/read-getter/send-and-refresh boilerplate across `switch.py`, `number.py`, `select.py`, and `sensor.py` into one shared contract on `Z906Entity`, driven by a declarative per-platform spec table instead of hand-written classes.

**Architecture:** `base_entity.py` gains an `EntitySpec` frozen dataclass (name, unique_id_suffix, get_endpoint, cast) and three shared methods on `Z906Entity` — `available`, `_read()`, `_send_and_settle(commands, *, optimistic_value=None)`. Each platform subclasses `EntitySpec` with its own write-side fields (command-builders) and replaces its hand-written entity classes with one generic class driven by a list of spec rows — following the pattern `number.py`'s existing `VOLUME_ENTITIES` table already uses. A "command" is a `(endpoint, params)` pair; `_send_and_settle` fans a list of them out concurrently via `asyncio.gather`, checks **every** result (fixing today's silently-swallowed partial failures in the power-on 3-command bundle), then either triggers a coordinator refresh or writes an optimistic value directly.

**Tech Stack:** Python 3.12, Home Assistant custom component conventions, `dataclasses`, `asyncio`. Tests use `pytest` + `pytest-asyncio` (auto mode) + `pytest-homeassistant-custom-component` for HA-compatible imports, with a lightweight `types.SimpleNamespace` fake coordinator — no real Home Assistant runtime is spun up for these tests.

## Global Constraints

- No new **runtime** dependency: `manifest.json`'s `requirements: []` stays empty. `pytest-homeassistant-custom-component` is test-only, pinned in `requirements_test.txt`, never referenced by the component itself.
- Follow the existing relative-import convention (`.const`, `.base_entity`, `.coordinator`) — no absolute `custom_components.z906_api...` imports inside the component itself (tests import that way; production code does not).
- Preserve the existing `unique_id` format exactly: `f"{host}-{unique_id_suffix}"`. Existing Home Assistant installs must not get duplicate/renamed entities after this change.
- Preserve `device_info` exactly as-is (keyed by `(DOMAIN, host)`).
- All `Spec` dataclasses are `@dataclass(frozen=True)`.
- HA minimum version floor stays `2024.11.0` (`hacs.json`) — this refactor does not require raising it.
- Every production file keeps its module-level docstring style (one-line or short docstring at top).

---

## File Structure

```
custom_components/z906_api/
  base_entity.py   — MODIFY: adds EntitySpec, generic available/_read/_send_and_settle
  const.py         — MODIFY: drops the INPUT_SET/INPUT_STATE string-alias
  switch.py        — REWRITE: SwitchSpec + SWITCH_ENTITIES + one Z906Switch class
  number.py        — REWRITE: NumberSpec + VOLUME_ENTITIES + one Z906Number class
  select.py        — REWRITE: SelectSpec + SELECT_ENTITIES + one Z906Select class
  sensor.py        — REWRITE: SensorSpec + SENSOR_ENTITIES + one Z906Sensor class
tests/
  __init__.py      — CREATE: empty
  conftest.py      — CREATE: registers pytest-homeassistant-custom-component
  test_base_entity.py — CREATE
  test_switch.py       — CREATE
  test_number.py       — CREATE
  test_select.py       — CREATE
  test_sensor.py       — CREATE
requirements_test.txt  — CREATE
pyproject.toml          — CREATE: pytest config
.github/workflows/validate.yml — MODIFY: add a pytest job
CLAUDE.md — MODIFY: rewrite Architecture/REST-contract sections, add Testing section
README.md — MODIFY: fix stale "range 0–255" volume text
```

Every production file in `custom_components/z906_api/` not listed above (`__init__.py`, `coordinator.py`, `config_flow.py`, `icons.json`, `manifest.json`, `strings.json`, `translations/en.json`) is untouched by this plan.

---

### Task 1: Test infrastructure

**Files:**
- Create: `requirements_test.txt`
- Create: `pyproject.toml`
- Create: `tests/__init__.py`
- Create: `tests/conftest.py`
- Test: `tests/test_infra_sanity.py` (deleted at the end of this task — it exists only to prove the harness works before Task 2 relies on it)

**Interfaces:**
- Produces: a working `pytest` invocation from the repo root that later tasks' test files can rely on.

- [ ] **Step 1: Create `requirements_test.txt`**

```
pytest-homeassistant-custom-component==0.13.205
```

- [ ] **Step 2: Create `pyproject.toml`**

```toml
[tool.pytest.ini_options]
asyncio_mode = "auto"
asyncio_default_fixture_loop_scope = "function"
```

- [ ] **Step 3: Create `tests/__init__.py`**

Empty file.

- [ ] **Step 4: Create `tests/conftest.py`**

```python
"""Shared test fixtures for the z906_api test suite."""

pytest_plugins = "pytest_homeassistant_custom_component"
```

- [ ] **Step 5: Write a throwaway sanity test**

Create `tests/test_infra_sanity.py`:

```python
"""Throwaway check that the test harness is wired up. Deleted at the end of Task 1."""


def test_pytest_runs():
    assert True
```

- [ ] **Step 6: Install test dependencies and run**

```bash
pip install -r requirements_test.txt
pytest tests/ -v
```

Expected: `tests/test_infra_sanity.py::test_pytest_runs PASSED`, `1 passed`.

- [ ] **Step 7: Delete the sanity test**

```bash
rm tests/test_infra_sanity.py
```

- [ ] **Step 8: Commit**

```bash
git add requirements_test.txt pyproject.toml tests/__init__.py tests/conftest.py
git commit -m "test: add pytest + pytest-homeassistant-custom-component infrastructure"
```

---

### Task 2: Deepen base_entity.py

**Files:**
- Modify: `custom_components/z906_api/base_entity.py`
- Test: `tests/test_base_entity.py`

**Interfaces:**
- Consumes: `Endpoints` from `.const` (unchanged), `Z906Coordinator` from `.coordinator` (unchanged — only used for type-hinting `Z906Entity.__init__`, not constructed in tests).
- Produces (used by Tasks 3–6):
  - `EntitySpec` — frozen dataclass: `name: str`, `unique_id_suffix: str`, `get_endpoint: Endpoints | None`, `cast: Callable[[Any], Any]`.
  - `Command` — type alias `tuple[str, list[tuple[str, Any]]]`, i.e. `(endpoint, params)`.
  - `Z906Entity.__init__(self, coordinator, host: str, spec: EntitySpec)` — now takes `spec` as a required third argument (was `(coordinator, host)` only).
  - `Z906Entity.available` (property) — `True` iff `super().available` and (`spec.get_endpoint is None` or `coordinator.data.get(spec.get_endpoint) is not None`).
  - `Z906Entity._read(self)` — returns `spec.cast(value)` if the endpoint has data, else `None`.
  - `Z906Entity._send_and_settle(self, commands: list[Command], *, optimistic_value: bool | None = None)` — async. Sends all commands concurrently; if any result is `None`, logs a warning and returns without refreshing; otherwise writes `optimistic_value` via `async_write_ha_state()` if given, else calls `coordinator.async_request_refresh()`.
  - `Z906Entity._attr_name`, `_attr_unique_id`, `_attr_translation_key` are now set generically in `__init__` from `spec.name`, `f"{host}-{spec.unique_id_suffix}"`, and `spec.unique_id_suffix` respectively — platform files no longer set these themselves.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_base_entity.py`:

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_base_entity.py -v
```

Expected: `ImportError: cannot import name 'EntitySpec' from 'custom_components.z906_api.base_entity'` (it doesn't exist yet).

- [ ] **Step 3: Rewrite `base_entity.py`**

```python
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
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/test_base_entity.py -v
```

Expected: 8 tests, all `PASSED`.

- [ ] **Step 5: Commit**

```bash
git add custom_components/z906_api/base_entity.py tests/test_base_entity.py
git commit -m "refactor: deepen Z906Entity with a declarative EntitySpec contract"
```

**Note:** after this step, `switch.py`, `number.py`, `select.py`, `sensor.py` are broken (they still call `Z906Entity.__init__(coordinator, host)` with two args, and `Z906Entity` now requires three). This is expected — Tasks 3–6 fix each in turn. Do not run the full test suite until Task 6 is done; run only the file under test in each task.

---

### Task 3: Rewrite switch.py

**Files:**
- Modify: `custom_components/z906_api/switch.py`
- Test: `tests/test_switch.py`

**Interfaces:**
- Consumes: `EntitySpec`, `Command`, `Z906Entity` from `.base_entity` (Task 2); `Endpoints`, `DOMAIN` from `.const`.
- Produces: `SwitchSpec(EntitySpec)` — adds `on: Callable[[], list[Command]]`, `off: Callable[[], list[Command]]`, `optimistic: bool = False`. `SWITCH_ENTITIES: list[SwitchSpec]`. `Z906Switch(Z906Entity, SwitchEntity)` — one class for both Power and Mute.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_switch.py`:

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_switch.py -v
```

Expected: `ImportError: cannot import name 'SWITCH_ENTITIES' from 'custom_components.z906_api.switch'`.

- [ ] **Step 3: Rewrite `switch.py`**

```python
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
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/test_switch.py -v
```

Expected: 8 tests, all `PASSED`.

- [ ] **Step 5: Commit**

```bash
git add custom_components/z906_api/switch.py tests/test_switch.py
git commit -m "refactor: drive switch.py from a declarative SwitchSpec table"
```

---

### Task 4: Rewrite number.py

**Files:**
- Modify: `custom_components/z906_api/number.py`
- Test: `tests/test_number.py`

**Interfaces:**
- Consumes: `EntitySpec`, `Command`, `Z906Entity` from `.base_entity` (Task 2).
- Produces: `NumberSpec(EntitySpec)` — adds `write: Callable[[float], list[Command]]`. `VOLUME_ENTITIES: list[NumberSpec]`. `Z906Number(Z906Entity, NumberEntity)`.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_number.py`:

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_number.py -v
```

Expected: `ImportError` — `number.py` still uses the old `(name, unique_id_suffix, get_endpoint, set_endpoint)` tuple shape, not `NumberSpec`.

- [ ] **Step 3: Rewrite `number.py`**

```python
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
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/test_number.py -v
```

Expected: 6 tests, all `PASSED`.

- [ ] **Step 5: Commit**

```bash
git add custom_components/z906_api/number.py tests/test_number.py
git commit -m "refactor: drive number.py from a declarative NumberSpec table"
```

---

### Task 5: Rewrite select.py and drop the INPUT_SET alias

**Files:**
- Modify: `custom_components/z906_api/const.py`
- Modify: `custom_components/z906_api/select.py`
- Test: `tests/test_select.py`

**Interfaces:**
- Consumes: `EntitySpec`, `Command`, `Z906Entity` from `.base_entity` (Task 2).
- Produces: `SelectSpec(EntitySpec)` — adds `options: dict[str, int]`, `write: Callable[[int], list[Command]]`. `SELECT_ENTITIES: list[SelectSpec]`. `Z906Select(Z906Entity, SelectEntity)`.

**Background:** `const.py` currently declares both `INPUT_STATE = "/input"` and `INPUT_SET = "/input"` — identical string values. Because `Endpoints` is a `StrEnum`, the second declaration becomes a silent alias of the first (`Endpoints.INPUT_SET is Endpoints.INPUT_STATE` is `True`; `INPUT_SET` doesn't even appear in `list(Endpoints)`). `select.py`'s new write-builder makes the path-building explicit (`f"{Endpoints.INPUT_STATE}/{value}"`), so the separate `INPUT_SET` name is no longer needed at all.

- [ ] **Step 1: Drop `INPUT_SET` from `const.py`**

In `custom_components/z906_api/const.py`, remove this line (it's a dead alias of `INPUT_STATE`, not a distinct endpoint):

```python
    INPUT_SET = "/input"
```

The `Endpoints` class should now read:

```python
from enum import StrEnum

DOMAIN = "z906_api"

class Endpoints(StrEnum):
    POWER_STATE = "/power"
    POWER_ON = "/power/on"
    POWER_OFF = "/power/off"
    TEMPERATURE = "/temperature"
    INPUT_STATE = "/input"
    INPUT_ENABLE = "/input/enable"
    VOLUME_MAIN = "/volume/main"
    VOLUME_MAIN_SET = "/volume/main/set"
    VOLUME_CENTER = "/volume/center"
    VOLUME_CENTER_SET = "/volume/center/set"
    VOLUME_REAR = "/volume/rear"
    VOLUME_REAR_SET = "/volume/rear/set"
    VOLUME_SUBWOOFER = "/volume/subwoofer"
    VOLUME_SUBWOOFER_SET = "/volume/subwoofer/set"
    MUTE_ON = "/mute/on"
    MUTE_OFF = "/mute/off"
```

- [ ] **Step 2: Confirm no other file references `INPUT_SET`**

```bash
grep -rn "INPUT_SET" custom_components/
```

Expected: no output (only `select.py` referenced it, and Step 4 below rewrites that file).

- [ ] **Step 3: Write the failing tests**

Create `tests/test_select.py`:

```python
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
```

- [ ] **Step 4: Run tests to verify they fail**

```bash
pytest tests/test_select.py -v
```

Expected: `ImportError: cannot import name 'SELECT_ENTITIES' from 'custom_components.z906_api.select'`.

- [ ] **Step 5: Rewrite `select.py`**

```python
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
```

- [ ] **Step 6: Run tests to verify they pass**

```bash
pytest tests/test_select.py -v
```

Expected: 5 tests, all `PASSED`.

- [ ] **Step 7: Commit**

```bash
git add custom_components/z906_api/const.py custom_components/z906_api/select.py tests/test_select.py
git commit -m "refactor: drive select.py from a declarative SelectSpec table, drop INPUT_SET alias"
```

---

### Task 6: Rewrite sensor.py

**Files:**
- Modify: `custom_components/z906_api/sensor.py`
- Test: `tests/test_sensor.py`

**Interfaces:**
- Consumes: `EntitySpec`, `Z906Entity` from `.base_entity` (Task 2).
- Produces: `SensorSpec(EntitySpec)` — no additional fields (read-only). `SENSOR_ENTITIES: list[SensorSpec]`. `Z906Sensor(Z906Entity, SensorEntity)`.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_sensor.py`:

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_sensor.py -v
```

Expected: `ImportError: cannot import name 'SENSOR_ENTITIES' from 'custom_components.z906_api.sensor'`.

- [ ] **Step 3: Rewrite `sensor.py`**

```python
"""Sensor platform: read-only temperature, driven by a declarative spec table."""

from dataclasses import dataclass

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.const import CONF_HOST

from .base_entity import EntitySpec, Z906Entity
from .const import DOMAIN, Endpoints


@dataclass(frozen=True)
class SensorSpec(EntitySpec):
    """A read-only entity. No write side."""


SENSOR_ENTITIES = [
    SensorSpec(
        name="Temperature",
        unique_id_suffix="temperature",
        get_endpoint=Endpoints.TEMPERATURE,
        cast=float,
    ),
]


async def async_setup_entry(hass, entry, async_add_entities):
    """Set up sensors from config entry."""
    host = entry.data[CONF_HOST]
    coordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([Z906Sensor(coordinator, host, spec) for spec in SENSOR_ENTITIES])


class Z906Sensor(Z906Entity, SensorEntity):
    """A read-only sensor for the Logitech Z906, driven by SensorSpec."""

    _attr_native_unit_of_measurement = "°C"
    _attr_device_class = SensorDeviceClass.TEMPERATURE
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_entity_registry_enabled_default = False

    @property
    def native_value(self):
        return self._read()
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/test_sensor.py -v
```

Expected: 2 tests, all `PASSED`.

- [ ] **Step 5: Run the full suite**

```bash
pytest tests/ -v
```

Expected: 29 tests total, all `PASSED` (8 base_entity + 8 switch + 6 number + 5 select + 2 sensor).

- [ ] **Step 6: Commit**

```bash
git add custom_components/z906_api/sensor.py tests/test_sensor.py
git commit -m "refactor: drive sensor.py from a declarative SensorSpec table"
```

---

### Task 7: Add pytest to CI

**Files:**
- Modify: `.github/workflows/validate.yml`

**Interfaces:**
- Consumes: `requirements_test.txt` (Task 1).

- [ ] **Step 1: Add a `pytest` job**

In `.github/workflows/validate.yml`, add a third job alongside `hassfest` and `hacs`:

```yaml
name: Validate

on:
  push:
  pull_request:
  workflow_dispatch:

jobs:
  hassfest:
    name: Hassfest
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: home-assistant/actions/hassfest@master

  hacs:
    name: HACS
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: hacs/action@main
        with:
          category: integration
          ignore: brands

  pytest:
    name: Pytest
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
      - run: pip install -r requirements_test.txt
      - run: pytest
```

- [ ] **Step 2: Verify the workflow file is valid YAML**

```bash
python3 -c "import yaml; yaml.safe_load(open('.github/workflows/validate.yml'))" && echo "valid YAML"
```

Expected: `valid YAML`.

- [ ] **Step 3: Commit**

```bash
git add .github/workflows/validate.yml
git commit -m "ci: run pytest alongside hassfest and HACS validation"
```

---

### Task 8: Update docs

**Files:**
- Modify: `CLAUDE.md`
- Modify: `README.md`

**Interfaces:** None — documentation only.

- [ ] **Step 1: Replace CLAUDE.md's "no test suite" claim**

In `CLAUDE.md`, find this sentence in the "What this is" section:

```markdown
There is no build system, test suite, or linter configured in this repo. It is loaded by running
it inside a Home Assistant instance.
```

Replace with:

```markdown
There is no build system or linter configured in this repo; it is loaded by running it inside a
Home Assistant instance. A unit test suite covering the shared entity contract lives in `tests/`
— see [Testing](#testing) below.
```

- [ ] **Step 2: Rewrite the Architecture section**

Replace the entire `## Architecture` section with:

```markdown
## Architecture

- `__init__.py` — entry point. `async_setup_entry` builds a `Z906Coordinator`, does
  `async_config_entry_first_refresh()`, stores the **coordinator** (not `entry.data`) in
  `hass.data[DOMAIN][entry_id]`, and forwards setup to the platforms
  `SWITCH, NUMBER, SELECT, SENSOR`.
- `const.py` — `DOMAIN` and the `Endpoints(StrEnum)` catalog of every REST path. Prefer referencing
  `Endpoints.*` over hardcoding paths.
- `coordinator.py` — `Z906Coordinator(DataUpdateCoordinator)`, the single I/O choke point:
  - `async_send(endpoint, params=[])` — aiohttp GET to `http://{host}{endpoint}`, 8s timeout,
    returns parsed JSON or `None` on any error (logs and swallows exceptions rather than raising).
    Used for both polling and commands.
  - `_async_update_data()` — fetches every read endpoint (`POLLED_ENDPOINTS`) concurrently via
    `asyncio.gather` once per 30s cycle and returns a `dict[Endpoints, value | None]`. Because
    per-endpoint failures resolve to `None` rather than raising, the coordinator itself always
    "succeeds" — entities determine their own availability by checking their endpoint's value.
- `base_entity.py` — the shared contract every platform builds on:
  - `EntitySpec` — a frozen dataclass every entity is declared from: `name`, `unique_id_suffix`,
    `get_endpoint` (the `Endpoints` member to read, or `None` for write-only entities), and `cast`
    (raw value → HA-facing value). Each platform subclasses it with its own write-side fields
    (see below).
  - `Z906Entity(CoordinatorEntity[Z906Coordinator])` — takes a `coordinator`, `host`, and an
    `EntitySpec`, and implements the read/available/write contract once for all platforms:
    `available` (coordinator alive, and the spec's `get_endpoint` has data or is `None`), `_read()`
    (cast the endpoint's current value), and `_send_and_settle(commands, *, optimistic_value=None)`
    — sends one or more `(endpoint, params)` commands concurrently, warns and leaves state alone if
    **any** fails, otherwise requests a coordinator refresh or (if `optimistic_value` is given)
    writes state directly. `device_info` is also provided here, keyed by `(DOMAIN, host)`.
- Platform files each define one generic entity class and a table of specs — adding an entity means
  adding a row, not a class:
  - `switch.py` — `SwitchSpec` (adds `on`/`off` command-builders and `optimistic: bool`);
    `SWITCH_ENTITIES` has Power (`get_endpoint=POWER_STATE`, `on` fires power/input-enable/mute-off
    concurrently) and Mute (`get_endpoint=None`, `optimistic=True`, so it renders via
    `_attr_assumed_state` instead of coordinator data). One `Z906Switch` class serves both.
  - `number.py` — `NumberSpec` (adds a `write(value) -> commands` builder). `VOLUME_ENTITIES` holds
    Main/Subwoofer/Center/Rear; UI range is **0–100%**, backed by a 0–255 raw endpoint via
    `_raw_to_percent`/`_percent_to_raw`. One `Z906Number` class serves all four, with a dynamic
    volume icon based on level.
  - `select.py` — `SelectSpec` (adds `options: dict[str, int]` and a `write` builder that appends
    the target input ID to `Endpoints.INPUT_STATE`'s path). One `Z906Select` class.
  - `sensor.py` — `SensorSpec` (no write fields — read-only). `Z906Sensor` is **disabled by
    default** (`_attr_entity_registry_enabled_default = False`).
- `icons.json` — per-entity default MDI icons (keyed by `translation_key`, which `Z906Entity` sets
  to each spec's `unique_id_suffix`).
- `manifest.json` — HA integration manifest (`config_flow: true`). `hacs.json` pins the minimum
  supported Home Assistant version — currently `2024.11.0`, required by the reconfigure-flow
  helpers (`_get_reconfigure_entry`, `_abort_if_unique_id_mismatch`) used in `config_flow.py`.
```

- [ ] **Step 3: Rewrite the REST contract section's "adding a property" guidance**

Replace the `## REST contract (important)` section with:

```markdown
## REST contract (important)

The bridge is expected to return JSON of the shape `{"value": <n>}` for every **read** endpoint.
The coordinator polls all read endpoints once per cycle (see `coordinator.py`); if a response is
falsy or missing `"value"`, that endpoint's entry is `None` and any entity depending on it reports
itself `unavailable`. **Set** endpoints receive the value as a query param, e.g.
`[("value", int(value))]`, or — for `select.py` — as a path segment. When adding a new controllable
property: add its paths to `Endpoints`, add the read endpoint to `coordinator.POLLED_ENDPOINTS` if
it needs polling, then add one row to the relevant platform's spec table (e.g. `SWITCH_ENTITIES`,
`VOLUME_ENTITIES`) — a new hand-written entity class is only needed if the property doesn't fit
any existing platform's spec shape.

## Testing

`tests/` covers the shared `Z906Entity` contract (`available`/`_read`/`_send_and_settle`) and each
platform's spec table (command-builders, casts) using a lightweight fake coordinator
(`types.SimpleNamespace` — no real Home Assistant runtime needed). Install `requirements_test.txt`
and run `pytest`. CI runs the suite alongside hassfest/HACS validation.
```

- [ ] **Step 4: Fix README.md's stale volume range**

In `README.md`, the entities table has four rows reading `Range 0–255, slider.`:

```markdown
| number   | Main Volume           | Range 0–255, slider.                                           |
| number   | Subwoofer Volume      | Range 0–255, slider.                                           |
| number   | Center Volume         | Range 0–255, slider.                                           |
| number   | Rear Volume           | Range 0–255, slider.                                           |
```

Replace all four with the actual UI-facing range:

```markdown
| number   | Main Volume           | 0–100%, slider (backed by a 0–255 raw value on the bridge).   |
| number   | Subwoofer Volume      | 0–100%, slider (backed by a 0–255 raw value on the bridge).   |
| number   | Center Volume         | 0–100%, slider (backed by a 0–255 raw value on the bridge).   |
| number   | Rear Volume           | 0–100%, slider (backed by a 0–255 raw value on the bridge).   |
```

- [ ] **Step 5: Commit**

```bash
git add CLAUDE.md README.md
git commit -m "docs: describe the EntitySpec architecture, fix stale volume-range text"
```

---

## Self-Review

**Spec coverage:**
- Declarative tables for all 4 platforms — Tasks 3–6. ✓
- Command-builder write shape, `_send_and_settle` checking all gathered results — Task 2. ✓
- Dataclass row structure (not tuples) — `EntitySpec`/`SwitchSpec`/`NumberSpec`/`SelectSpec`/`SensorSpec` in Tasks 2–6. ✓
- One dataclass per platform, not a unified shape — confirmed, `SensorSpec` carries no write fields. ✓
- Shared base dataclass (`EntitySpec`) with platform specs extending it — Task 2 + Tasks 3–6. ✓
- Test suite added now (`pytest-homeassistant-custom-component`) — Task 1, tests woven through Tasks 2–6. ✓
- All four platforms migrated in one pass — Tasks 3–6, sequential in this single plan. ✓
- Swallowed power-on failure fixed as a byproduct — Task 2's `_send_and_settle` checks every result; verified by `test_power_turn_on_skips_refresh_if_any_of_three_fails` in Task 3. ✓
- INPUT_SET/INPUT_STATE alias dropped — Task 5. ✓
- Stale 0–255 docs fixed — Task 8. ✓
- CI runs the new suite — Task 7. ✓

**Placeholder scan:** No TBD/TODO markers; every step shows complete file content or exact commands with expected output.

**Type consistency:** `Command = tuple[str, list[tuple[str, Any]]]` (Task 2) is used identically in `SwitchSpec.on`/`off`, `NumberSpec.write`, `SelectSpec.write` (Tasks 3–5). `EntitySpec` field names (`name`, `unique_id_suffix`, `get_endpoint`, `cast`) match across every subclass and every test. `Z906Entity.__init__(coordinator, host, spec)` signature is consistent across all five call sites (base_entity's own tests, and each platform's `async_setup_entry`).

All code in this plan was written against and verified passing (29/29 tests) in a working prototype before this plan was finalized.
