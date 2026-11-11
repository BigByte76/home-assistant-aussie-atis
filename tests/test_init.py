"""Integration tests: setup, unload, partial failures, config and options flows."""

from pathlib import Path

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry
from pytest_homeassistant_custom_component.test_util.aiohttp import AiohttpClientMocker

from custom_components.aussie_atis.const import BASE_URL, CONF_AIRPORTS, DOMAIN
from homeassistant.config_entries import SOURCE_USER, ConfigEntryState
from homeassistant.const import STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import device_registry as dr

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations: None) -> None:
    """Allow Home Assistant to load the integration from custom_components."""


def mock_page(aioclient_mock: AiohttpClientMocker, code: str, status: int = 200) -> None:
    text = (FIXTURES / f"{code}.html").read_text() if status == 200 else ""
    aioclient_mock.get(BASE_URL.format(code=code), text=text, status=status)


async def setup_entry(hass: HomeAssistant, airports: list[str]) -> MockConfigEntry:
    entry = MockConfigEntry(domain=DOMAIN, title="Australian ATIS", data={CONF_AIRPORTS: airports})
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry


async def test_setup_creates_individual_sensors_and_unloads(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    mock_page(aioclient_mock, "yssy")
    mock_page(aioclient_mock, "ybbn")
    entry = await setup_entry(hass, ["YSSY", "YBBN"])
    assert entry.state is ConfigEntryState.LOADED

    expected = {
        "sensor.yssy_atis": "A",
        "sensor.yssy_atis_arrival_runways": "34L, 34R",
        "sensor.yssy_atis_departure_runways": "34L, 34R",
        "sensor.yssy_atis_wind_speed": "10",
        "sensor.yssy_atis_max_tailwind": "5",
        "sensor.yssy_atis_qnh": "1016",
        "sensor.yssy_atis_temperature": "21",
        "sensor.ybbn_atis_arrival_runways": "01L, 01R",
        "sensor.ybbn_atis_departure_runways": "01R",
        "sensor.ybbn_atis_significant_weather": "TS IN AREA",
    }
    for entity_id, state in expected.items():
        assert hass.states.get(entity_id).state == state, entity_id

    main = hass.states.get("sensor.yssy_atis")
    assert main.attributes["airport"] == "Sydney"
    assert main.attributes["atis"].startswith("ATIS YSSY A")
    assert hass.states.get("sensor.yssy_atis_issued").state == "2026-11-11T09:13:00+00:00"

    # The TAF is longer than a state allows: truncated state, full attribute.
    taf = hass.states.get("sensor.ybbn_atis_taf")
    assert len(taf.state) <= 255
    assert len(taf.attributes["full_text"]) > 255

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.NOT_LOADED


async def test_one_airport_failing_only_affects_that_airport(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    mock_page(aioclient_mock, "yssy")
    mock_page(aioclient_mock, "ybbn", status=500)
    entry = await setup_entry(hass, ["YSSY", "YBBN"])
    assert entry.state is ConfigEntryState.LOADED
    assert hass.states.get("sensor.yssy_atis").state == "A"
    assert hass.states.get("sensor.ybbn_atis").state == STATE_UNAVAILABLE


async def test_all_airports_failing_retries_setup(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    mock_page(aioclient_mock, "yssy", status=503)
    entry = await setup_entry(hass, ["YSSY"])
    assert entry.state is ConfigEntryState.SETUP_RETRY


async def test_airport_without_atis(hass: HomeAssistant, aioclient_mock: AiohttpClientMocker) -> None:
    mock_page(aioclient_mock, "ybas")
    await setup_entry(hass, ["YBAS"])
    assert hass.states.get("sensor.ybas_atis").state == "unknown"
    assert hass.states.get("sensor.ybas_atis_metar").state.startswith("METAR YBAS")


async def test_options_flow_removes_deselected_airport(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    mock_page(aioclient_mock, "yssy")
    mock_page(aioclient_mock, "ybbn")
    entry = await setup_entry(hass, ["YSSY", "YBBN"])
    device_registry = dr.async_get(hass)
    assert device_registry.async_get_device(identifiers={(DOMAIN, "YBBN")}) is not None

    result = await hass.config_entries.options.async_init(entry.entry_id)
    assert result["type"] is FlowResultType.FORM

    result = await hass.config_entries.options.async_configure(result["flow_id"], {CONF_AIRPORTS: []})
    assert result["errors"] == {"base": "no_airports"}

    result = await hass.config_entries.options.async_configure(result["flow_id"], {CONF_AIRPORTS: ["YSSY"]})
    assert result["type"] is FlowResultType.CREATE_ENTRY
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.LOADED
    assert device_registry.async_get_device(identifiers={(DOMAIN, "YBBN")}) is None
    assert hass.states.get("sensor.ybbn_atis") is None
    assert hass.states.get("sensor.yssy_atis").state == "A"


async def test_config_flow(hass: HomeAssistant, aioclient_mock: AiohttpClientMocker) -> None:
    mock_page(aioclient_mock, "ymml")
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": SOURCE_USER})
    assert result["type"] is FlowResultType.FORM

    result = await hass.config_entries.flow.async_configure(result["flow_id"], {CONF_AIRPORTS: []})
    assert result["errors"] == {"base": "no_airports"}

    result = await hass.config_entries.flow.async_configure(result["flow_id"], {CONF_AIRPORTS: ["YMML"]})
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == {CONF_AIRPORTS: ["YMML"]}
    await hass.async_block_till_done()
    assert hass.states.get("sensor.ymml_atis_departure_runways").state == "27"

    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": SOURCE_USER})
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "single_instance_allowed"
