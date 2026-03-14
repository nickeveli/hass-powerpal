"""
Custom integration to integrate Powerpal with Home Assistant.

For more details about this integration, please refer to
https://github.com/nickeveli/hass-powerpal
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.typing import ConfigType
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.components.recorder.models import StatisticData, StatisticMetaData

try:
    from homeassistant.components.recorder.models import StatisticMeanType

    HAS_MEAN_TYPE = True
except ImportError:
    HAS_MEAN_TYPE = False

from homeassistant.components.recorder.statistics import (
    async_import_statistics,
)

from .api import PowerpalApiClient, PowerpalError
from .const import (
    CONF_AUTH_KEY,
    CONF_DEVICE_ID,
    DOMAIN,
    PLATFORMS,
    SERVICE_BACKFILL,
)

SCAN_INTERVAL = timedelta(seconds=60)

_LOGGER = logging.getLogger(__name__)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up this integration using YAML is not supported."""
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Powerpal from a config entry."""
    hass.data.setdefault(DOMAIN, {})

    auth_key = entry.data[CONF_AUTH_KEY]
    device_id = entry.data[CONF_DEVICE_ID]

    session = async_get_clientsession(hass)
    client = PowerpalApiClient(session, auth_key, device_id)

    coordinator = PowerpalDataUpdateCoordinator(hass, client=client)
    await coordinator.async_config_entry_first_refresh()

    hass.data[DOMAIN][entry.entry_id] = {
        "coordinator": coordinator,
        "client": client,
    }

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(async_reload_entry))

    # Register backfill service (once)
    if not hass.services.has_service(DOMAIN, SERVICE_BACKFILL):
        _register_services(hass)

    return True


def _register_services(hass: HomeAssistant) -> None:
    """Register Powerpal services."""

    async def handle_backfill(call: ServiceCall) -> None:
        """Handle the backfill_history service call."""
        device_id = call.data["device_id"]
        days_back = call.data.get("days", 365)
        sample_minutes = call.data.get("sample_minutes", 30)

        # Find the right client by device_id
        client: PowerpalApiClient | None = None
        for entry_data in hass.data[DOMAIN].values():
            if not isinstance(entry_data, dict):
                continue
            c = entry_data.get("client")
            if c and c.device_id == device_id:
                client = c
                break

        if client is None:
            _LOGGER.error("No Powerpal integration found for device_id: %s", device_id)
            return

        # Get current device total to calculate proper offset
        try:
            device_data = await client.get_device_data()
            current_total_wh = device_data.get("total_watt_hours", 0)
        except PowerpalError as err:
            _LOGGER.error("Error fetching device data for offset calculation: %s", err)
            return

        now = datetime.now(timezone.utc)
        end = now
        start = now - timedelta(days=days_back)

        _LOGGER.info(
            "Starting Powerpal backfill for %s: %d days back, %d min sample "
            "(current device total: %.2f kWh)",
            device_id,
            days_back,
            sample_minutes,
            current_total_wh / 1000.0,
        )

        # Fetch in monthly chunks (50k record limit per request)
        all_readings: list[dict] = []
        chunk_start = start
        while chunk_start < end:
            chunk_end = min(chunk_start + timedelta(days=30), end)
            try:
                readings = await client.get_time_series(
                    start=int(chunk_start.timestamp()),
                    end=int(chunk_end.timestamp()),
                    sample=sample_minutes,
                )
                if readings:
                    all_readings.extend(readings)
                    _LOGGER.info(
                        "Fetched %d readings from %s to %s",
                        len(readings),
                        chunk_start.date(),
                        chunk_end.date(),
                    )
            except PowerpalError as err:
                _LOGGER.error("Error fetching backfill data: %s", err)
                # Continue with next chunk
            chunk_start = chunk_end

        if not all_readings:
            _LOGGER.warning("No historical data returned from Powerpal API")
            return

        # Sort by timestamp
        all_readings.sort(key=lambda r: r["timestamp"])

        # Build statistics for the total consumption sensor
        statistic_id = "sensor.powerpal_total_consumption"
        meta_kwargs = {
            "has_mean": False,
            "has_sum": True,
            "name": "Powerpal Total Consumption",
            "source": "recorder",
            "statistic_id": statistic_id,
            "unit_of_measurement": "kWh",
        }
        if HAS_MEAN_TYPE:
            meta_kwargs["mean_type"] = StatisticMeanType.NONE
        metadata = StatisticMetaData(**meta_kwargs)

        # Bucket readings into hourly intervals (recorder requires
        # timestamps at the top of each hour)
        hourly_buckets: dict[datetime, float] = {}
        for reading in all_readings:
            ts = datetime.fromtimestamp(reading["timestamp"], tz=timezone.utc)
            # Truncate to the top of the hour
            hour_start = ts.replace(minute=0, second=0, microsecond=0)
            wh = reading.get("watt_hours", 0) or 0
            hourly_buckets[hour_start] = hourly_buckets.get(hour_start, 0.0) + wh

        # Calculate the offset so that backfilled data aligns with
        # the actual device total. The time series gives us deltas
        # (watt_hours per interval). The sum of all deltas = energy
        # consumed during the backfill window. The offset is everything
        # consumed BEFORE the backfill window started.
        series_total_wh = sum(hourly_buckets.values())
        offset_wh = current_total_wh - series_total_wh

        _LOGGER.info(
            "Backfill offset calculation: device total=%.2f kWh, "
            "series total=%.2f kWh, offset (pre-backfill)=%.2f kWh",
            current_total_wh / 1000.0,
            series_total_wh / 1000.0,
            offset_wh / 1000.0,
        )

        # Build cumulative statistics from the hourly buckets.
        # 'state' = actual meter reading (offset + running total) in kWh
        # 'sum' = cumulative consumption since start of backfill in kWh
        # Both use the same accumulation so the Energy Dashboard can
        # compute correct deltas across the boundary with live data.
        cumulative_wh = 0.0
        statistics: list[StatisticData] = []

        for hour_start in sorted(hourly_buckets.keys()):
            cumulative_wh += hourly_buckets[hour_start]
            statistics.append(
                StatisticData(
                    start=hour_start,
                    state=(offset_wh + cumulative_wh) / 1000.0,
                    sum=cumulative_wh / 1000.0,
                )
            )

        async_import_statistics(hass, metadata, statistics)

        _LOGGER.info(
            "Backfill complete: imported %d statistics for %s (%.2f kWh total)",
            len(statistics),
            device_id,
            cumulative_wh / 1000.0,
        )

    hass.services.async_register(
        DOMAIN,
        SERVICE_BACKFILL,
        handle_backfill,
        schema=vol.Schema(
            {
                vol.Required("device_id"): str,
                vol.Optional("days", default=365): vol.All(
                    int, vol.Range(min=1, max=1095)
                ),
                vol.Optional("sample_minutes", default=30): vol.All(
                    int, vol.Range(min=1, max=1440)
                ),
            }
        ),
    )


class PowerpalDataUpdateCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Class to manage fetching data from the API."""

    def __init__(self, hass: HomeAssistant, client: PowerpalApiClient) -> None:
        """Initialize."""
        self.api = client
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=SCAN_INTERVAL,
        )

    async def _async_update_data(self) -> dict[str, Any]:
        """Update data via library."""
        try:
            return await self.api.get_device_data()
        except PowerpalError as err:
            raise UpdateFailed(f"Error communicating with Powerpal API: {err}") from err


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Handle removal of an entry."""
    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unloaded:
        hass.data[DOMAIN].pop(entry.entry_id)
    return unloaded


async def async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload config entry."""
    await hass.config_entries.async_reload(entry.entry_id)
