"""Sensor platform for Powerpal."""
from __future__ import annotations

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfEnergy, UnitOfPower
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import ATTRIBUTION, CONF_DEVICE_ID, DOMAIN, NAME


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Powerpal sensor platform."""
    coordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]
    async_add_entities(
        [
            PowerpalTotalConsumptionSensor(coordinator, entry),
            PowerpalLiveConsumptionSensor(coordinator, entry),
        ]
    )


class PowerpalSensor(CoordinatorEntity, SensorEntity):
    """Base Powerpal Sensor class."""

    _attr_attribution = ATTRIBUTION
    _attr_has_entity_name = True

    def __init__(self, coordinator, config_entry: ConfigEntry) -> None:
        super().__init__(coordinator)
        self._config_entry = config_entry
        self._device_id = config_entry.data[CONF_DEVICE_ID]

    @property
    def device_info(self) -> DeviceInfo:
        return DeviceInfo(
            identifiers={(DOMAIN, self._device_id)},
            name=NAME,
            manufacturer=NAME,
            model=self._device_id,
        )

    @property
    def extra_state_attributes(self) -> dict:
        return {
            "device_id": self._device_id,
            "integration": DOMAIN,
        }


class PowerpalTotalConsumptionSensor(PowerpalSensor):
    """Sensor for total cumulative energy consumption."""

    _attr_name = "Total Consumption"
    _attr_device_class = SensorDeviceClass.ENERGY
    _attr_state_class = SensorStateClass.TOTAL_INCREASING
    _attr_native_unit_of_measurement = UnitOfEnergy.KILO_WATT_HOUR
    _attr_icon = "mdi:transmission-tower"

    @property
    def unique_id(self) -> str:
        return f"powerpal-total-{self._device_id}"

    @property
    def native_value(self) -> float | None:
        if self.coordinator.data is None:
            return None
        total_wh = self.coordinator.data.get("total_watt_hours")
        if total_wh is None:
            return None
        return total_wh / 1000.0


class PowerpalLiveConsumptionSensor(PowerpalSensor):
    """Sensor for live (latest reading) power consumption."""

    _attr_name = "Live Consumption"
    _attr_device_class = SensorDeviceClass.POWER
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = UnitOfPower.WATT
    _attr_icon = "mdi:flash"

    @property
    def unique_id(self) -> str:
        return f"powerpal-live-{self._device_id}"

    @property
    def native_value(self) -> float | None:
        if self.coordinator.data is None:
            return None
        last_wh = self.coordinator.data.get("last_reading_watt_hours")
        if last_wh is None:
            return None
        # last_reading_watt_hours is Wh consumed in the last 60s interval
        # Multiply by 60 to convert Wh/min to W
        return last_wh * 60
