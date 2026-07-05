# Logitech Z906 API

A Home Assistant custom component that controls a Logitech Z906 5.1 speaker system through a
separate HTTP/REST bridge.

This integration does **not** talk to the Z906 directly — it expects a bridge running somewhere on
your network that exposes the Z906's serial/RS-232 control protocol over a small REST API (see
[REST contract](#rest-contract) below). This component is built against the REST API provided by
[LewisSmallwood/IoT-Logitech-Z906](https://github.com/LewisSmallwood/IoT-Logitech-Z906); set that
up first and point this integration at its host. Building/running the bridge itself is out of scope
for this repo.

- `iot_class`: `local_polling`
- No extra Python dependencies — uses only libraries bundled with Home Assistant (`aiohttp`,
  `voluptuous`, `async_timeout`).

## Entities

| Platform | Entity                | Notes                                                        |
| -------- | --------------------- | ------------------------------------------------------------- |
| switch   | Power                 | Polls `/power`. Turning on fires power-on/input-enable/mute-off concurrently. |
| switch   | Mute                  | Command-only, does not poll.                                  |
| number   | Main Volume           | Range 0–255, slider.                                           |
| number   | Subwoofer Volume      | Range 0–255, slider.                                           |
| number   | Center Volume         | Range 0–255, slider.                                           |
| number   | Rear Volume           | Range 0–255, slider.                                           |
| select   | Input Source          | TRS 5.1 / RCA 2.0 / Optical 1 / Optical 2 / Coaxial.           |
| sensor   | Temperature           | Disabled by default; enable it in the entity registry if your bridge reports temperature. |

All entities are grouped under one device, keyed by the configured host.

## Installation

### HACS (custom repository)

This integration isn't in the default HACS store. Add it as a custom repository:

1. In Home Assistant, open **HACS → Integrations**.
2. Click the **⋮** menu → **Custom repositories**.
3. Add `https://github.com/mkverse/z906_api`, category **Integration**.
4. Find **Logitech Z906 API** in HACS and install it.
5. Restart Home Assistant.

### Manual

Copy (or symlink) `custom_components/z906_api` from this repo into your Home Assistant config
directory, so the final path is:

```
<HA config dir>/custom_components/z906_api/
```

Then restart Home Assistant.

## Configuration

Configuration is done entirely through the UI:

**Settings → Devices & Services → Add Integration → "Logitech Z906 API"**

You'll be asked for the **host** (hostname or IP, optionally with a port) of your REST bridge. The
config flow validates it by issuing a GET to `/power` and expects a JSON response containing a
`value` field. The same host can't be added twice, and if the bridge's address ever changes you can
update it in place via the integration's **Reconfigure** option instead of removing and re-adding it.

## REST contract

The bridge is expected to expose:

| Endpoint                  | Method | Purpose                          |
| -------------------------- | ------ | --------------------------------- |
| `/power`                   | GET    | Current power state                |
| `/power/on`, `/power/off`  | GET    | Power on/off                       |
| `/temperature`              | GET    | Current temperature                |
| `/input`                    | GET    | Current input source                |
| `/input/enable`             | GET    | Enable input                        |
| `/input/{id}`               | GET    | Select input `id`                   |
| `/volume/main[/set]`        | GET    | Get/set main volume                 |
| `/volume/center[/set]`      | GET    | Get/set center volume               |
| `/volume/rear[/set]`        | GET    | Get/set rear volume                 |
| `/volume/subwoofer[/set]`   | GET    | Get/set subwoofer volume            |
| `/mute/on`, `/mute/off`      | GET    | Mute on/off                         |

All **read** endpoints must return JSON of the shape `{"value": <n>}`. If the response is falsy or
missing `value`, the entity is marked `unavailable`. **Set** endpoints receive the value as a query
parameter, e.g. `/volume/main/set?value=128`.

## License

MIT — see [LICENSE](LICENSE).
