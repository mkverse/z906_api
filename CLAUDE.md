# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

A Home Assistant **custom component** (`domain: z906_api`) that controls a Logitech Z906 5.1
speaker system through a separate HTTP/REST bridge. `iot_class` is `local_polling` and the
component has **no Python `requirements`** — it uses only libraries already bundled with Home
Assistant (`aiohttp`, `voluptuous`, `async_timeout`).

There is no build system, test suite, or linter configured in this repo. It is loaded by running
it inside a Home Assistant instance.

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
- `base_entity.py` — `Z906Entity(CoordinatorEntity[Z906Coordinator])`, the shared base for
  **every** entity. Provides `device_info` keyed by `(DOMAIN, host)` so all entities group under
  one HA device, plus `async_send_command(endpoint, params)` which delegates to
  `coordinator.async_send`. Entities read state from `self.coordinator.data.get(endpoint)` and
  override `available` to require their specific endpoint's value is not `None`.
- Platform files, each subclassing `Z906Entity` + a HA entity type. None of them poll individually
  or define `async_update` anymore — state comes from the shared coordinator:
  - `switch.py` — `Z906PowerSwitch` (state from `POWER_STATE`; turn-on fires
    power/input-enable/mute-off concurrently via `asyncio.gather`, then requests a coordinator
    refresh) and `Z906MuteSwitch` (no read endpoint; optimistic state, `_attr_assumed_state`).
  - `number.py` — Main / Subwoofer / Center / Rear volume sliders, range **0–255**, dynamic
    volume icon based on level.
  - `select.py` — `Z906InputSelect`; `INPUT_OPTIONS` maps display names → integer input IDs.
  - `sensor.py` — `Z906TemperatureSensor`, **disabled by default**
    (`_attr_entity_registry_enabled_default = False`).
- `icons.json` — per-entity default MDI icons (keyed by `translation_key`).
- `manifest.json` — HA integration manifest (`config_flow: true`). `hacs.json` pins the minimum
  supported Home Assistant version — currently `2024.11.0`, required by the reconfigure-flow
  helpers (`_get_reconfigure_entry`, `_abort_if_unique_id_mismatch`) used in `config_flow.py`.

## REST contract (important)

The bridge is expected to return JSON of the shape `{"value": <n>}` for every **read** endpoint.
The coordinator polls all read endpoints once per cycle (see `coordinator.py`); if a response is
falsy or missing `"value"`, that endpoint's entry is `None` and any entity depending on it reports
itself `unavailable`. **Set** endpoints receive the value as a query param, e.g.
`async_send_command(Endpoints.VOLUME_MAIN_SET, [("value", int(value))])`. When adding a new
controllable property: add its paths to `Endpoints`, add the read endpoint to
`coordinator.POLLED_ENDPOINTS` if it needs polling, then follow the existing entity pattern.

