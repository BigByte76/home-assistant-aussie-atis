"""Integration tests for the ATFM Daily Plan sensors."""

from datetime import UTC, datetime, timedelta
from pathlib import Path

from freezegun.api import FrozenDateTimeFactory
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry, async_fire_time_changed
from pytest_homeassistant_custom_component.test_util.aiohttp import AiohttpClientMocker

from custom_components.aussie_atis.const import ATFM_URL, BASE_URL, CONF_AIRPORTS, CONF_ATFM, DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import entity_registry as er

FIXTURES = Path(__file__).parent / "fixtures"
PLAN = (FIXTURES / "atfm_daily_plan.pdf").read_bytes()
# 13:30 in Sydney on the plan day.
NOW = datetime(2026, 11, 18, 2, 30, tzinfo=UTC)


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations: None) -> None:
    """Allow Home Assistant to load the integration from custom_components."""


@pytest.fixture(autouse=True)
async def sydney_time(hass: HomeAssistant, freezer: FrozenDateTimeFactory) -> None:
    await hass.config.async_set_time_zone("Australia/Sydney")
    freezer.move_to(NOW)


async def setup(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    airports: list[str],
    atfm_status: int = 200,
    atfm: bool = True,
) -> MockConfigEntry:
    for code in airports:
        aioclient_mock.get(BASE_URL.format(code=code.lower()), text=(FIXTURES / "yssy.html").read_text())
    aioclient_mock.get(ATFM_URL, content=PLAN if atfm_status == 200 else b"", status=atfm_status)
    entry = MockConfigEntry(domain=DOMAIN, data={CONF_AIRPORTS: airports, CONF_ATFM: atfm})
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    # The first ATFM download runs as a background task.
    await hass.async_block_till_done(wait_background_tasks=True)
    return entry


def atfm_requests(aioclient_mock: AiohttpClientMocker) -> int:
    return sum(1 for _, url, _, _ in aioclient_mock.mock_calls if str(url) == ATFM_URL)


async def test_sensors_in_local_time(hass: HomeAssistant, aioclient_mock: AiohttpClientMocker) -> None:
    await setup(hass, aioclient_mock, ["YSSY", "YBBN", "YPPH", "YBAS"])

    plan = hass.states.get("sensor.yssy_atis_atfm_plan")
    assert plan.state == "2026-11-18"
    assert plan.attributes["version"] == 1
    forecast = plan.attributes["forecast"]
    assert forecast[0] == {
        "start": "2026-11-18T06:00:00+11:00",
        "end": "2026-11-18T07:00:00+11:00",
        "runway_mode": "34 DVAB",
        "runways": ["34"],
        "mode_code": "DVAB",
        "arrival_rate": 34,
        "notes": [1],
    }
    assert plan.attributes["attribution"] == "ATFM Daily Plan provided by Airservices Australia"

    mode = hass.states.get("sensor.yssy_atis_atfm_runway_mode")
    assert mode.state == "34 DVAA"
    assert mode.attributes["runways"] == ["34"]
    assert mode.attributes["next_change"] == "2026-11-18T22:00:00+11:00"
    assert mode.attributes["next_runway_mode"] == "34 DVAB"

    rate = hass.states.get("sensor.yssy_atis_atfm_arrival_rate")
    assert rate.state == "44"
    assert rate.attributes["unit_of_measurement"] == "arrivals/h"
    assert rate.attributes["next_change"] == "2026-11-18T20:00:00+11:00"
    assert rate.attributes["next_arrival_rate"] == 38

    brisbane = hass.states.get("sensor.ybbn_atis_atfm_runway_mode")
    assert brisbane.state == "01 DEP VMC"
    # Brisbane's plan times are shown in Home Assistant's time zone, not Brisbane's.
    assert brisbane.attributes["next_change"] == "2026-11-18T22:00:00+11:00"

    gdp = hass.states.get("sensor.ypph_atis_atfm_ground_delay_program")
    assert gdp.state == "GDP-A"
    assert gdp.attributes["programs"] == [
        {"name": "GDP-A", "start": "2026-11-18T11:00:00+11:00", "end": "2026-11-19T01:00:00+11:00"}
    ]
    assert gdp.attributes["affected_flights"] == 208
    assert gdp.attributes["average_ground_delay_minutes"] == 8.9
    assert hass.states.get("sensor.yssy_atis_atfm_ground_delay_program").state == "None"

    notes = hass.states.get("sensor.ybbn_atis_atfm_notes")
    assert notes.state.startswith("A weak ridge")
    assert len(notes.state) <= 255
    assert notes.attributes["full_text"].endswith("22-01Z.")
    assert notes.attributes["sm_notes"][0]["start"] == "2026-11-18T09:00:00+11:00"

    # Only the four airports in the plan get ATFM sensors.
    assert hass.states.get("sensor.ybas_atis_atfm_plan") is None
    assert hass.states.get("sensor.ybas_atis") is not None
    assert atfm_requests(aioclient_mock) == 1


async def test_updates_on_the_hour_without_downloading(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker, freezer: FrozenDateTimeFactory
) -> None:
    freezer.move_to(datetime(2026, 11, 17, 23, 30, tzinfo=UTC))
    await setup(hass, aioclient_mock, ["YSSY"])
    assert hass.states.get("sensor.yssy_atis_atfm_arrival_rate").state == "40"
    assert hass.states.get("sensor.yssy_atis_atfm_runway_mode").state == "34 DVAB"

    freezer.move_to(datetime(2026, 11, 18, 0, 0, 0, tzinfo=UTC))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)
    assert hass.states.get("sensor.yssy_atis_atfm_arrival_rate").state == "44"
    assert hass.states.get("sensor.yssy_atis_atfm_runway_mode").state == "34 DVAA"
    assert atfm_requests(aioclient_mock) == 1

    # After the plan ends the current values are unknown; the plan stays.
    freezer.move_to(datetime(2026, 11, 18, 12, 0, 0, tzinfo=UTC))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)
    assert hass.states.get("sensor.yssy_atis_atfm_arrival_rate").state == STATE_UNKNOWN
    assert hass.states.get("sensor.yssy_atis_atfm_runway_mode").state == STATE_UNKNOWN
    assert hass.states.get("sensor.yssy_atis_atfm_plan").state == "2026-11-18"


async def test_download_failure_does_not_block_setup(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker, freezer: FrozenDateTimeFactory
) -> None:
    entry = await setup(hass, aioclient_mock, ["YSSY"], atfm_status=503)
    assert entry.state is ConfigEntryState.LOADED
    assert hass.states.get("sensor.yssy_atis").state == "A"
    assert hass.states.get("sensor.yssy_atis_atfm_runway_mode").state == STATE_UNAVAILABLE

    # Retried after 30 minutes rather than 6 hours.
    aioclient_mock.clear_requests()
    aioclient_mock.get(BASE_URL.format(code="yssy"), text=(FIXTURES / "yssy.html").read_text())
    aioclient_mock.get(ATFM_URL, content=PLAN)
    freezer.tick(timedelta(minutes=31))
    async_fire_time_changed(hass)
    # Interval refreshes run as background tasks.
    await hass.async_block_till_done(wait_background_tasks=True)
    assert hass.states.get("sensor.yssy_atis_atfm_runway_mode").state == "34 DVAA"


async def test_failure_keeps_last_plan(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker, freezer: FrozenDateTimeFactory
) -> None:
    await setup(hass, aioclient_mock, ["YSSY"])
    aioclient_mock.clear_requests()
    aioclient_mock.get(BASE_URL.format(code="yssy"), text=(FIXTURES / "yssy.html").read_text())
    aioclient_mock.get(ATFM_URL, status=500)

    freezer.tick(timedelta(hours=6, minutes=1))
    async_fire_time_changed(hass)
    # Interval refreshes run as background tasks.
    await hass.async_block_till_done(wait_background_tasks=True)
    assert atfm_requests(aioclient_mock) == 1
    # 08:31 UTC: still read from the plan downloaded earlier.
    assert hass.states.get("sensor.yssy_atis_atfm_arrival_rate").state == "44"


async def test_unreadable_plan_is_a_failure(hass: HomeAssistant, aioclient_mock: AiohttpClientMocker) -> None:
    aioclient_mock.get(BASE_URL.format(code="yssy"), text=(FIXTURES / "yssy.html").read_text())
    aioclient_mock.get(ATFM_URL, text="<html>maintenance</html>")
    entry = MockConfigEntry(domain=DOMAIN, data={CONF_AIRPORTS: ["YSSY"], CONF_ATFM: True})
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    # The first ATFM download runs as a background task.
    await hass.async_block_till_done(wait_background_tasks=True)
    assert hass.states.get("sensor.yssy_atis_atfm_plan").state == STATE_UNAVAILABLE


async def test_no_download_without_atfm_airports(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    entry = await setup(hass, aioclient_mock, ["YBAS"])
    assert entry.runtime_data.atfm is None
    assert atfm_requests(aioclient_mock) == 0


async def test_off_by_default(hass: HomeAssistant, aioclient_mock: AiohttpClientMocker) -> None:
    # Entries from before the option existed have no "atfm" key.
    aioclient_mock.get(BASE_URL.format(code="yssy"), text=(FIXTURES / "yssy.html").read_text())
    entry = MockConfigEntry(domain=DOMAIN, data={CONF_AIRPORTS: ["YSSY"]})
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done(wait_background_tasks=True)
    assert entry.runtime_data.atfm is None
    assert hass.states.get("sensor.yssy_atis").state == "A"
    assert hass.states.get("sensor.yssy_atis_atfm_plan") is None
    assert atfm_requests(aioclient_mock) == 0


async def test_options_toggle_adds_and_removes_sensors(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    entry = await setup(hass, aioclient_mock, ["YSSY"], atfm=False)
    entity_registry = er.async_get(hass)
    assert hass.states.get("sensor.yssy_atis_atfm_runway_mode") is None

    result = await hass.config_entries.options.async_init(entry.entry_id)
    assert result["data_schema"]({CONF_AIRPORTS: ["YSSY"]})[CONF_ATFM] is False
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {CONF_AIRPORTS: ["YSSY"], CONF_ATFM: True}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    await hass.async_block_till_done(wait_background_tasks=True)
    assert hass.states.get("sensor.yssy_atis_atfm_runway_mode").state == "34 DVAA"
    assert entity_registry.async_get("sensor.yssy_atis_atfm_runway_mode") is not None

    result = await hass.config_entries.options.async_init(entry.entry_id)
    assert result["data_schema"]({CONF_AIRPORTS: ["YSSY"]})[CONF_ATFM] is True
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {CONF_AIRPORTS: ["YSSY"], CONF_ATFM: False}
    )
    await hass.async_block_till_done(wait_background_tasks=True)
    assert hass.states.get("sensor.yssy_atis_atfm_runway_mode") is None
    assert entity_registry.async_get("sensor.yssy_atis_atfm_runway_mode") is None
    # The ATIS sensors are untouched.
    assert entity_registry.async_get("sensor.yssy_atis") is not None
    assert hass.states.get("sensor.yssy_atis").state == "A"
