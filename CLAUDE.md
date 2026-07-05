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

Internal imports use the **absolute** form `from custom_components.z906_api.… import …`
(e.g. `base_entity.py`, `switch.py`, `config_flow.py`). This means the code must be installed at:

```
<HA config dir>/custom_components/z906_api/
```

To develop: place (or symlink) this directory there, then restart Home Assistant and add the
integration via the UI (Settings → Devices & Services → Add Integration → "Logitech Z906 API").
The config flow (`config_flow.py`) asks only for a host and validates it by GETting `/power`.
Note the mixed import style — `base_entity.py` uses a relative `.const` import while the platform
files use absolute `custom_components.z906_api.*`; keep new imports consistent with the file you
are editing.

## Architecture

- `__init__.py` — entry point. `async_setup_entry` stores `entry.data` in
  `hass.data[DOMAIN][entry_id]` and forwards setup to the platforms `SWITCH, NUMBER, SELECT, SENSOR`.
- `const.py` — `DOMAIN` and the `Endpoints(StrEnum)` catalog of every REST path. Prefer referencing
  `Endpoints.*` over hardcoding paths (a few call sites currently hardcode, e.g. `/power/off` in
  `switch.py` and `/input/{value}` in `select.py`).
- `base_entity.py` — `BaseZ906Entity`, the shared base for **every** entity. Provides:
  - `device_info` keyed by `(DOMAIN, host)` so all entities group under one HA device.
  - `_send_request(endpoint, params=[])` — the single choke point for all I/O: aiohttp GET to
    `http://{host}{endpoint}`, 8s timeout, returns parsed JSON or `None` on any error (it logs and
    swallows exceptions rather than raising).
- Platform files, each subclassing `BaseZ906Entity` + a HA entity type:
  - `switch.py` — `Z906PowerSwitch` (polls `/power`; turn-on fires power/input-enable/mute-off
    concurrently via `asyncio.gather`) and `Z906MuteSwitch` (no polling).
  - `number.py` — Main / Subwoofer / Center / Rear volume sliders, range **0–255**, dynamic
    volume icon based on level.
  - `select.py` — `Z906InputSelect`; `INPUT_OPTIONS` maps display names → integer input IDs.
  - `sensor.py` — `Z906TemperatureSensor`, **disabled by default**
    (`entity_registry_enabled_default = False`).
- `icons.json` — per-entity default MDI icons (keyed by `translation_key`).
- `manifest.json` — HA integration manifest (`config_flow: true`).

## REST contract (important)

The bridge is expected to return JSON of the shape `{"value": <n>}` for every **read** endpoint.
Entities poll in `async_update` and read `data["value"]`; if the response is falsy or missing
`"value"`, the entity marks itself `unavailable`. **Set** endpoints receive the value as a query
param, e.g. `_send_request(Endpoints.VOLUME_MAIN_SET, [("value", int(value))])`. When adding a new
controllable property, add its paths to `Endpoints`, then follow the existing poll/command pattern.

