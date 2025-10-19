"""ATIS sensors."""
from __future__ import annotations

import asyncio
import logging
from datetime import timedelta

from homeassistant.components.sensor import SensorEntity
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
)
from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from .const import DOMAIN
from .fetch_atis import fetch_atis, parse_atis

_LOGGER = logging.getLogger(__name__)

SCAN_INTERVAL = timedelta(minutes=15)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities):
    airports = entry.data.get("airports", [])
    sensors = []

    for code in airports:
        coordinator = ATISDataCoordinator(hass, code)
        await coordinator.async_config_entry_first_refresh()
        sensors.append(AtisSensor(coordinator, code))

    async_add_entities(sensors, update_before_add=True)


class ATISDataCoordinator(DataUpdateCoordinator):
    """Coordinator for ATIS data."""

    def __init__(self, hass: HomeAssistant, airport_code: str):
        super().__init__(
            hass,
            _LOGGER,
            name=f"ATIS {airport_code}",
            update_interval=SCAN_INTERVAL,
        )
        self.airport_code = airport_code

    async def _async_update_data(self):
        raw = await fetch_atis(self.airport_code)
        return parse_atis(raw)


class AtisSensor(CoordinatorEntity, SensorEntity):
    """Main ATIS sensor per airport."""

    def __init__(self, coordinator: ATISDataCoordinator, airport_code: str):
        super().__init__(coordinator)
        self.airport_code = airport_code
        self._attr_unique_id = f"atis_{airport_code.lower()}"
        self._attr_name = f"ATIS {airport_code}"

    @property
    def native_value(self):
        data = self.coordinator.data
        return data.get("weather", "Unknown")

    @property
    def extra_state_attributes(self):
        return self.coordinator.data
