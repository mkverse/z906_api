# Changelog

All notable changes to this project are documented here.

## [0.3.0] - 2026-07-06

### Changed
- Volume entities (Main, Subwoofer, Center, Rear) now display and accept 0-100% in the Home Assistant UI instead of the raw 0-255 device range. The bridge protocol and REST endpoints are unchanged internally; only the entity's displayed range/unit changed, so no re-adding of entities is needed.

## [0.2.0]

### Changed
- Moved polling to a shared `DataUpdateCoordinator` instead of per-entity updates.
- Standardized internal imports to the relative form.
- Hardened the config flow, including support for reconfiguring an existing entry's host.

## [0.1.0]

### Added
- Initial release: switch, number, select, and sensor entities for controlling a Logitech Z906 speaker system through its HTTP/REST bridge.
