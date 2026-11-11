"""Sensor platform for the Australian ATIS integration.

Each configured airport becomes a device ("YSSY ATIS") with one sensor per ATIS
field, e.g. ``sensor.yssy_atis`` (information letter), ``sensor.yssy_atis_wind``,
``sensor.yssy_atis_arrival_runways``.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import DEGREE, UnitOfPressure, UnitOfSpeed, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import StateType
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import AtisConfigEntry
from .atis_parser import AirportInfo, AtisReport
from .const import AIRPORTS, ATTRIBUTION, BASE_URL, DOMAIN, MANUFACTURER
from .coordinator import AtisCoordinator

# Home Assistant states are limited to 255 characters.
MAX_STATE_LENGTH = 255

# Coordinator-driven entities: the coordinator limits requests, not the platform.
PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class AtisSensorEntityDescription(SensorEntityDescription):
    """Describes an ATIS sensor."""

    value_fn: Callable[[AirportInfo], StateType | datetime]
    # Expose the untruncated text as a "full_text" attribute.
    long_text: bool = False


def _atis(getter: Callable[[AtisReport], Any]) -> Callable[[AirportInfo], Any]:
    """Wrap a getter on the ATIS report, returning None when there is no ATIS."""
    return lambda info: getter(info.atis) if info.atis else None


def _join(runways: tuple[str, ...]) -> str | None:
    return ", ".join(runways) or None


KNOTS_SENSOR = {
    "device_class": SensorDeviceClass.WIND_SPEED,
    "native_unit_of_measurement": UnitOfSpeed.KNOTS,
    "state_class": SensorStateClass.MEASUREMENT,
}

SENSORS: tuple[AtisSensorEntityDescription, ...] = (
    AtisSensorEntityDescription(
        key="atis",
        translation_key="atis",
        name=None,  # Main sensor: takes the device name, e.g. sensor.yssy_atis.
        value_fn=_atis(lambda a: a.code),
    ),
    AtisSensorEntityDescription(
        key="issued",
        translation_key="issued",
        device_class=SensorDeviceClass.TIMESTAMP,
        value_fn=_atis(lambda a: a.issued),
    ),
    AtisSensorEntityDescription(
        key="approach",
        translation_key="approach",
        long_text=True,
        value_fn=_atis(lambda a: a.approach),
    ),
    AtisSensorEntityDescription(
        key="runway",
        translation_key="runway",
        long_text=True,
        value_fn=_atis(lambda a: a.runway),
    ),
    AtisSensorEntityDescription(
        key="arrival_runways",
        translation_key="arrival_runways",
        value_fn=_atis(lambda a: _join(a.arrival_runways)),
    ),
    AtisSensorEntityDescription(
        key="departure_runways",
        translation_key="departure_runways",
        value_fn=_atis(lambda a: _join(a.departure_runways)),
    ),
    AtisSensorEntityDescription(
        key="surface_condition",
        translation_key="surface_condition",
        long_text=True,
        value_fn=_atis(lambda a: a.surface_condition),
    ),
    AtisSensorEntityDescription(
        key="operational_info",
        translation_key="operational_info",
        long_text=True,
        value_fn=_atis(lambda a: a.operational_info),
    ),
    AtisSensorEntityDescription(
        key="wind",
        translation_key="wind",
        long_text=True,
        value_fn=_atis(lambda a: a.wind),
    ),
    AtisSensorEntityDescription(
        key="wind_direction",
        translation_key="wind_direction",
        native_unit_of_measurement=DEGREE,
        value_fn=_atis(lambda a: a.wind_direction),
    ),
    AtisSensorEntityDescription(
        key="wind_speed",
        translation_key="wind_speed",
        value_fn=_atis(lambda a: a.wind_speed),
        **KNOTS_SENSOR,
    ),
    AtisSensorEntityDescription(
        key="wind_gust",
        translation_key="wind_gust",
        value_fn=_atis(lambda a: a.wind_gust),
        **KNOTS_SENSOR,
    ),
    AtisSensorEntityDescription(
        key="max_crosswind",
        translation_key="max_crosswind",
        value_fn=_atis(lambda a: a.max_crosswind),
        **KNOTS_SENSOR,
    ),
    AtisSensorEntityDescription(
        key="max_tailwind",
        translation_key="max_tailwind",
        value_fn=_atis(lambda a: a.max_tailwind),
        **KNOTS_SENSOR,
    ),
    AtisSensorEntityDescription(
        key="visibility",
        translation_key="visibility",
        long_text=True,
        value_fn=_atis(lambda a: a.visibility),
    ),
    AtisSensorEntityDescription(
        key="weather",
        translation_key="weather",
        long_text=True,
        value_fn=_atis(lambda a: a.weather),
    ),
    AtisSensorEntityDescription(
        key="cloud",
        translation_key="cloud",
        long_text=True,
        value_fn=_atis(lambda a: a.cloud),
    ),
    AtisSensorEntityDescription(
        key="temperature",
        translation_key="temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=_atis(lambda a: a.temperature),
    ),
    AtisSensorEntityDescription(
        key="qnh",
        translation_key="qnh",
        device_class=SensorDeviceClass.PRESSURE,
        native_unit_of_measurement=UnitOfPressure.HPA,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=_atis(lambda a: a.qnh),
    ),
    AtisSensorEntityDescription(
        key="sigwx",
        translation_key="sigwx",
        long_text=True,
        value_fn=_atis(lambda a: a.sigwx),
    ),
    AtisSensorEntityDescription(
        key="metar",
        translation_key="metar",
        long_text=True,
        value_fn=lambda info: info.metar,
    ),
    AtisSensorEntityDescription(
        key="taf",
        translation_key="taf",
        long_text=True,
        value_fn=lambda info: info.taf,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: AtisConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Create sensors for every selected airport."""
    coordinator = entry.runtime_data
    async_add_entities(
        AtisSensor(coordinator, airport, description)
        for airport in coordinator.airports
        for description in SENSORS
    )


class AtisSensor(CoordinatorEntity[AtisCoordinator], SensorEntity):
    """A single ATIS field for one airport."""

    _attr_has_entity_name = True
    _attr_attribution = ATTRIBUTION
    # Large text attributes would bloat the recorder database.
    _unrecorded_attributes = frozenset({"atis", "full_text"})

    entity_description: AtisSensorEntityDescription

    def __init__(
        self,
        coordinator: AtisCoordinator,
        airport: str,
        description: AtisSensorEntityDescription,
    ) -> None:
        """Initialise the sensor."""
        super().__init__(coordinator)
        self.entity_description = description
        self._airport = airport
        self._attr_unique_id = f"{airport}_{description.key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, airport)},
            name=f"{airport} ATIS",
            model=AIRPORTS.get(airport, airport),
            manufacturer=MANUFACTURER,
            entry_type=DeviceEntryType.SERVICE,
            configuration_url=BASE_URL.format(code=airport.lower()),
        )

    @property
    def _info(self) -> AirportInfo | None:
        return self.coordinator.data.get(self._airport)

    @property
    def available(self) -> bool:
        """Unavailable when this airport's last fetch failed."""
        return super().available and self._info is not None

    @property
    def native_value(self) -> StateType | datetime:
        """Return the sensor value, truncated to fit a Home Assistant state."""
        if (info := self._info) is None:
            return None
        value = self.entity_description.value_fn(info)
        if isinstance(value, str) and len(value) > MAX_STATE_LENGTH:
            return value[: MAX_STATE_LENGTH - 1] + "…"
        return value

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return the full text, and the whole broadcast on the main sensor."""
        if (info := self._info) is None:
            return None
        if self.entity_description.key == "atis":
            atis = info.atis
            return {
                "airport": AIRPORTS.get(self._airport, self._airport),
                "atis": atis.text if atis else None,
                "changed_fields": list(atis.changed_fields) if atis else [],
                "other_info": atis.other_info if atis else None,
            }
        if self.entity_description.long_text:
            return {"full_text": self.entity_description.value_fn(info)}
        return None
