"""Sensor platform for the Australian ATIS integration.

Each configured airport becomes a device ("YSSY ATIS") with one sensor per ATIS
field, e.g. ``sensor.yssy_atis`` (information letter), ``sensor.yssy_atis_wind``,
``sensor.yssy_atis_arrival_runways``.

Airports covered by the ATFM Daily Plan (YSSY, YMML, YBBN, YPPH) also get ATFM
sensors on the same device, e.g. ``sensor.yssy_atis_atfm_runway_mode``.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import DEGREE, UnitOfPressure, UnitOfSpeed, UnitOfTemperature
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.event import async_track_utc_time_change
from homeassistant.helpers.typing import StateType
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import dt as dt_util

from . import AtisConfigEntry
from .atfm_parser import ATFM_AIRPORTS, AirportPlan, DailyPlan, PlanHour, PlanNote
from .atis_parser import AirportInfo, AtisReport
from .const import AIRPORTS, ATFM_ATTRIBUTION, ATTRIBUTION, BASE_URL, DOMAIN, MANUFACTURER
from .coordinator import AtfmCoordinator, AtisCoordinator

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
    coordinator = entry.runtime_data.atis
    entities: list[SensorEntity] = [
        AtisSensor(coordinator, airport, description)
        for airport in coordinator.airports
        for description in SENSORS
    ]
    if (atfm := entry.runtime_data.atfm) is not None:
        entities.extend(
            AtfmSensor(atfm, airport, description)
            for airport in coordinator.airports
            if airport in ATFM_AIRPORTS
            for description in ATFM_SENSORS
        )
    async_add_entities(entities)


def _device_info(airport: str) -> DeviceInfo:
    """Return the device shared by an airport's ATIS and ATFM sensors."""
    return DeviceInfo(
        identifiers={(DOMAIN, airport)},
        name=f"{airport} ATIS",
        model=AIRPORTS.get(airport, airport),
        manufacturer=MANUFACTURER,
        entry_type=DeviceEntryType.SERVICE,
        configuration_url=BASE_URL.format(code=airport.lower()),
    )


def _truncate(value: Any) -> Any:
    """Shorten text to fit a Home Assistant state."""
    if isinstance(value, str) and len(value) > MAX_STATE_LENGTH:
        return value[: MAX_STATE_LENGTH - 1] + "…"
    return value


class AtisSensor(CoordinatorEntity[AtisCoordinator], SensorEntity):
    """A single ATIS field for one airport."""

    _attr_has_entity_name = True
    _attr_attribution = ATTRIBUTION
    # Large text attributes, and the static runway layout, would bloat the
    # recorder database.
    _unrecorded_attributes = frozenset({"atis", "full_text", "runways"})

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
        self._attr_device_info = _device_info(airport)

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
        return _truncate(self.entity_description.value_fn(info))

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
                # For dashboard cards that draw the airport: the active runways
                # as lists, and the layout of every runway.
                "arrival_runways": list(atis.arrival_runways) if atis else [],
                "departure_runways": list(atis.departure_runways) if atis else [],
                "runways": [runway.as_dict() for runway in info.runways],
            }
        if self.entity_description.long_text:
            return {"full_text": self.entity_description.value_fn(info)}
        return None


# ATFM Daily Plan sensors. Plan times are UTC; attributes give them in Home
# Assistant's local time zone as ISO 8601 strings.


@dataclass(frozen=True)
class AtfmContext:
    """What an ATFM sensor reads: the plan, the airport's part and the time."""

    plan: DailyPlan
    airport: AirportPlan
    now: datetime

    @property
    def hour(self) -> PlanHour | None:
        return self.airport.hour_at(self.now)


@dataclass(frozen=True, kw_only=True)
class AtfmSensorEntityDescription(SensorEntityDescription):
    """Describes an ATFM Daily Plan sensor."""

    value_fn: Callable[[AtfmContext], StateType | date]
    attrs_fn: Callable[[AtfmContext], dict[str, Any]]


def _local(value: datetime | None) -> str | None:
    return dt_util.as_local(value).isoformat() if value else None


def _note(note: PlanNote) -> dict[str, Any]:
    return {"number": note.number, "start": _local(note.start), "end": _local(note.end), "text": note.text}


def _hour(hour: PlanHour) -> dict[str, Any]:
    return {
        "start": _local(hour.start),
        "end": _local(hour.end),
        "runway_mode": hour.runway_mode,
        "runways": list(hour.runways),
        "mode_code": hour.mode_code,
        "arrival_rate": hour.arrival_rate,
        "notes": list(hour.notes),
    }


def _next(ctx: AtfmContext, attr: str, name: str) -> dict[str, Any]:
    """The next planned change of ``attr``: when, and the new value."""
    change = ctx.airport.next_change(ctx.now, attr)
    return {
        "next_change": _local(change.start) if change else None,
        name: getattr(change, attr) if change else None,
    }


def _current(attr: str) -> Callable[[AtfmContext], Any]:
    return lambda ctx: getattr(ctx.hour, attr) if ctx.hour else None


def _current_notes(ctx: AtfmContext) -> str | None:
    return " ".join(note.text for note in ctx.airport.notes_for(ctx.hour)) or None


ATFM_SENSORS: tuple[AtfmSensorEntityDescription, ...] = (
    AtfmSensorEntityDescription(
        key="atfm_plan",
        translation_key="atfm_plan",
        device_class=SensorDeviceClass.DATE,
        value_fn=lambda ctx: ctx.plan.plan_date,
        attrs_fn=lambda ctx: {
            "version": ctx.plan.version,
            "change_summary": ctx.plan.change_summary,
            "forecast": [_hour(hour) for hour in ctx.airport.hours],
        },
    ),
    AtfmSensorEntityDescription(
        key="atfm_runway_mode",
        translation_key="atfm_runway_mode",
        value_fn=_current("runway_mode"),
        attrs_fn=lambda ctx: {
            "runways": list(ctx.hour.runways) if ctx.hour else [],
            "mode_code": ctx.hour.mode_code if ctx.hour else None,
            **_next(ctx, "runway_mode", "next_runway_mode"),
        },
    ),
    AtfmSensorEntityDescription(
        key="atfm_arrival_rate",
        translation_key="atfm_arrival_rate",
        native_unit_of_measurement="arrivals/h",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=_current("arrival_rate"),
        attrs_fn=lambda ctx: _next(ctx, "arrival_rate", "next_arrival_rate"),
    ),
    AtfmSensorEntityDescription(
        key="atfm_ground_delay_program",
        translation_key="atfm_ground_delay_program",
        value_fn=lambda ctx: ", ".join(gdp.name for gdp in ctx.airport.ground_delay_programs) or "None",
        attrs_fn=lambda ctx: {
            "programs": [
                {"name": gdp.name, "start": _local(gdp.start), "end": _local(gdp.end)}
                for gdp in ctx.airport.ground_delay_programs
            ],
            "total_movements": ctx.airport.total_movements,
            "affected_flights": ctx.airport.affected_flights,
            "total_ground_delay_minutes": ctx.airport.total_ground_delay,
            "average_ground_delay_minutes": ctx.airport.average_ground_delay,
            "gdp_notes": ctx.airport.gdp_notes,
        },
    ),
    AtfmSensorEntityDescription(
        key="atfm_notes",
        translation_key="atfm_notes",
        value_fn=_current_notes,
        attrs_fn=lambda ctx: {
            "full_text": _current_notes(ctx),
            "metcdm_notes": [_note(note) for note in ctx.airport.metcdm_notes],
            "dlm_notes": [_note(note) for note in ctx.airport.dlm_notes],
            "sm_notes": [_note(note) for note in ctx.airport.sm_notes],
        },
    ),
)


class AtfmSensor(CoordinatorEntity[AtfmCoordinator], SensorEntity):
    """One ATFM Daily Plan value for one airport.

    Values for "now" change on the hour without a new download, so the state
    is rewritten at the start of every hour.
    """

    _attr_has_entity_name = True
    _attr_attribution = ATFM_ATTRIBUTION
    _unrecorded_attributes = frozenset({"forecast", "full_text", "metcdm_notes", "dlm_notes", "sm_notes"})

    entity_description: AtfmSensorEntityDescription

    def __init__(
        self,
        coordinator: AtfmCoordinator,
        airport: str,
        description: AtfmSensorEntityDescription,
    ) -> None:
        """Initialise the sensor."""
        super().__init__(coordinator)
        self.entity_description = description
        self._airport = airport
        self._attr_unique_id = f"{airport}_{description.key}"
        self._attr_device_info = _device_info(airport)

    async def async_added_to_hass(self) -> None:
        """Also update at the start of every hour."""
        await super().async_added_to_hass()
        self.async_on_remove(
            async_track_utc_time_change(self.hass, self._async_hour_changed, minute=0, second=0)
        )

    @callback
    def _async_hour_changed(self, now: datetime) -> None:
        self.async_write_ha_state()

    @property
    def _plan_context(self) -> AtfmContext | None:
        plan = self.coordinator.data
        if plan is None or (airport := plan.airports.get(self._airport)) is None:
            return None
        return AtfmContext(plan, airport, dt_util.utcnow())

    @property
    def available(self) -> bool:
        """Unavailable until a plan that covers this airport has been read."""
        return super().available and self._plan_context is not None

    @property
    def native_value(self) -> StateType | date:
        """Return the value for the current hour."""
        if (ctx := self._plan_context) is None:
            return None
        return _truncate(self.entity_description.value_fn(ctx))

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return the attributes, with times in local time."""
        if (ctx := self._plan_context) is None:
            return None
        return self.entity_description.attrs_fn(ctx)
