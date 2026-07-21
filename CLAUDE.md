# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

A Home Assistant **custom component** (`domain: z906_api`) that controls a Logitech Z906 5.1
speaker system through a separate HTTP/REST bridge. `iot_class` is `local_polling` and the
component has **no Python `requirements`** — it uses only libraries already bundled with Home
Assistant (`aiohttp`, `voluptuous`, `async_timeout`).

There is no build system or linter configured in this repo; it is loaded by running it inside a
Home Assistant instance. A unit test suite covering the shared entity contract lives in `tests/`
— see [Testing](#testing) below.

## Deployment / how it runs

Internal imports use the **relative** form (`.const`, `.base_entity`, `.coordinator`) throughout —
keep new imports consistent with this. The component still must be installed at:

```
<HA config dir>/custom_components/z906_api/
```

To develop: place (or symlink) this directory there, then restart Home Assistant and add the
integration via the UI (Settings → Devices & Services → Add Integration → "Logitech Z906 API").
The config flow (`config_flow.py`) asks only for a host, validates it by GETting `/power`, and
sets the host as the entry's `unique_id` (so the same host can't be added twice). It also exposes
`async_step_reconfigure` to change the host of an existing entry without deleting it.

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

