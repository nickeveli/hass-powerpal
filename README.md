# Powerpal for Home Assistant

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-41BDF5.svg)](https://github.com/hacs/integration)

A Home Assistant custom integration to fetch energy consumption data from your [Powerpal](https://www.powerpal.net/) device via the Powerpal cloud API.

This is a fork of [mindmelting/hass-powerpal](https://github.com/mindmelting/hass-powerpal) by [Lawrence (@mindmelting)](https://github.com/mindmelting), originally built on top of the [mindmelting.powerpal](https://github.com/mindmelting/powerpal) Python package.

## What's changed in this fork

The original integration stopped loading on newer versions of Home Assistant due to breaking changes in HA core and the external `mindmelting.powerpal` pip package failing to install. This fork addresses those issues and adds new functionality:

### Fixes

- **Removed external dependency** — the `mindmelting.powerpal` pip package has been replaced with a built-in API client, eliminating the "Invalid handler specified" error that prevented the integration from loading.
- **Updated to modern HA patterns** — replaced deprecated `CONNECTION_CLASS`, `asyncio.gather` unload pattern, and options flow `__init__` signature.
- **Config flow fixed** — renamed class, removed deprecated attributes, added duplicate device detection via `async_set_unique_id`.
- **Sensor null safety** — sensors now return `None` gracefully instead of crashing when API data is unavailable.
- **DeviceInfo** — sensors now use the proper `DeviceInfo` object instead of a raw dict.
- **Live consumption unit corrected** — changed from kW to W to accurately reflect the Wh-per-minute reading converted to instantaneous watts.
- **Statistics import** — uses `StatisticMeanType.NONE` to avoid deprecation warnings on HA 2025.10+.

### New features

- **Historical data backfill** — a new `powerpal.backfill_history` service action lets you import up to 3 years of historical energy data from the Powerpal cloud API into Home Assistant's long-term statistics, populating the Energy Dashboard with past data.

## Entities

| Entity | Type | Device class | Description |
|--------|------|-------------|-------------|
| Powerpal Total Consumption | Sensor | Energy (kWh) | Cumulative grid import energy. Use this in the Energy Dashboard under "Grid consumption". |
| Powerpal Live Consumption | Sensor | Power (W) | Instantaneous power draw based on the most recent 60-second reading. Useful for Lovelace cards but not selectable in the Energy Dashboard (by design — the dashboard requires energy sensors). |

## Installation

### HACS (recommended)

1. In HACS, go to **Integrations** → **⋮** (top right) → **Custom repositories**.
2. Add URL: `https://github.com/nickeveli/hass-powerpal`, Category: **Integration**.
3. Search for **Powerpal** and install.
4. Restart Home Assistant.

### Manual

1. Copy the `custom_components/powerpal/` folder into your Home Assistant `config/custom_components/` directory.
2. Restart Home Assistant.

## Configuration

1. Go to **Settings** → **Devices & Services** → **Add Integration**.
2. Search for **Powerpal**.
3. Enter your **API Authorization Key** and **Device ID**.

### Finding your API key and Device ID

Your API key and Device ID can be obtained from the Powerpal device itself over BLE using the [powerpal_ble tools](https://github.com/WeekendWarrior1/powerpal_ble), or by intercepting the Powerpal app's API traffic.

## Backfilling historical data

Once the integration is set up, you can import historical energy data into Home Assistant's long-term statistics so the Energy Dashboard shows past consumption.

1. Go to **Developer Tools** → **Actions** (or **Services** on older HA versions).
2. Search for `powerpal.backfill_history`.
3. Fill in the fields:

| Field | Required | Default | Description |
|-------|----------|---------|-------------|
| `device_id` | Yes | — | Your Powerpal device ID (8-character hex string, e.g. `00abcdef`). |
| `days` | No | 365 | How many days of history to fetch (max 1095 / ~3 years). |
| `sample_minutes` | No | 30 | Bucket size for readings. Use 30 for half-hourly, 60 for hourly. Smaller values give more detail but take longer. |

4. Click **Perform action**.

The backfill fetches data in monthly chunks from the Powerpal time series API and imports it as hourly statistics. Progress is logged — check **Settings** → **System** → **Logs** and filter for `powerpal`.

The backfill automatically calculates the correct offset from your device's lifetime total so that historical and live data join seamlessly. Re-running the backfill overwrites previous values, so it's safe to run multiple times.

## Energy Dashboard setup

The Powerpal measures grid import only (it counts LED pulses on your smart meter). To get the full energy flow diagram, pair it with a solar inverter integration:

| Dashboard slot | Sensor to use |
|---|---|
| **Grid consumption** | `sensor.powerpal_total_consumption` |
| **Return to grid** | Your inverter's export energy sensor |
| **Solar production** | Your inverter's total PV generation sensor |

## Credits

- **[Lawrence (@mindmelting)](https://github.com/mindmelting)** — original integration and the `mindmelting.powerpal` Python package.
- **[forfuncsake](https://github.com/forfuncsake/powerpal)** — Go client and Powerpal API documentation that inspired the original project.
- **[WeekendWarrior1](https://github.com/WeekendWarrior1/powerpal_ble)** — BLE documentation and ESPHome component for local Powerpal data retrieval.

## License

This project is licensed under the MIT License — see the original [LICENSE](LICENSE) file for details.
