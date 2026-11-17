"""Render the example dashboard cards against real fixture data.

The cards are Markdown cards whose content is a Home Assistant template, so
rendering them here catches template errors and entity ID drift.
"""

from datetime import UTC, datetime
from pathlib import Path

from freezegun.api import FrozenDateTimeFactory
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry
from pytest_homeassistant_custom_component.test_util.aiohttp import AiohttpClientMocker
import yaml

from custom_components.aussie_atis.const import ATFM_URL, BASE_URL, CONF_AIRPORTS, CONF_ATFM, DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.helpers.template import Template

ROOT = Path(__file__).parents[1]
FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations: None) -> None:
    """Allow Home Assistant to load the integration from custom_components."""


@pytest.fixture(autouse=True)
def mock_atfm_plan(aioclient_mock: AiohttpClientMocker) -> None:
    """Serve the ATFM Daily Plan, for tests that turn it on."""
    aioclient_mock.get(ATFM_URL, content=(FIXTURES / "atfm_daily_plan.pdf").read_bytes())


async def setup(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    codes: list[str],
    extra: tuple[str, ...] = (),
    atfm: bool = False,
) -> None:
    """Set up the airports in ``codes``, served from fixtures, plus ``extra`` ones mocked by the caller."""
    for code in codes:
        aioclient_mock.get(BASE_URL.format(code=code), text=(FIXTURES / f"{code}.html").read_text())
    airports = [c.upper() for c in codes] + list(extra)
    entry = MockConfigEntry(domain=DOMAIN, data={CONF_AIRPORTS: airports, CONF_ATFM: atfm})
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()


def render(hass: HomeAssistant, card: str, icao: str | None = None) -> str:
    content = yaml.safe_load((ROOT / "dashboards" / card).read_text())["content"]
    if icao:
        content = content.replace("set icao = 'yssy'", f"set icao = '{icao}'", 1)
    return Template(content, hass).async_render(parse_result=False)


async def test_airport_card(hass: HomeAssistant, aioclient_mock: AiohttpClientMocker) -> None:
    await setup(hass, aioclient_mock, ["yssy", "ybbn", "ybas"])

    sydney = render(hass, "atis-airport-card.yaml")
    assert "### ✈️ Sydney (YSSY)" in sydney
    assert "## Information A" in sydney
    assert "| 🛬 **Arrivals** | **34L, 34R** |" in sydney
    assert "| QNH | 1016 hPa 🔸 |" in sydney
    assert "INDEPENDENT PARL APPROACHES" in sydney
    assert "METAR YSSY" in sydney

    brisbane = render(hass, "atis-airport-card.yaml", "ybbn")
    assert "| 🛫 **Departures** | **01R** |" in brisbane
    assert "TS IN AREA" in brisbane
    # The full TAF comes from the full_text attribute, not the truncated state.
    assert "TAF3" in brisbane

    alice = render(hass, "atis-airport-card.yaml", "ybas")
    assert "No ATIS is being broadcast" in alice
    assert "METAR YBAS" in alice

    missing = render(hass, "atis-airport-card.yaml", "ymml")
    assert "No data" in missing


async def test_overview_card(hass: HomeAssistant, aioclient_mock: AiohttpClientMocker) -> None:
    await setup(hass, aioclient_mock, ["yssy", "ybbn"])
    rows = [line for line in render(hass, "atis-overview-card.yaml").splitlines() if line.startswith("| **")]
    assert rows == [
        "| **YBBN** Brisbane | P | 01L, 01R | 01R | 320/15, MAX XW 18 | 1018 |",
        "| **YSSY** Sydney | A | 34L, 34R | 34L, 34R | 100/10 KTS,TW 5 KTS | 1016 |",
    ]


async def test_atfm_plan_card(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker, freezer: FrozenDateTimeFactory
) -> None:
    await hass.config.async_set_time_zone("Australia/Sydney")
    freezer.move_to(datetime(2026, 11, 18, 2, 30, tzinfo=UTC))
    aioclient_mock.get(BASE_URL.format(code="ypph"), text=(FIXTURES / "yssy.html").read_text())
    await setup(hass, aioclient_mock, ["yssy", "ybas"], extra=("YPPH",), atfm=True)
    await hass.async_block_till_done(wait_background_tasks=True)

    sydney = render(hass, "atfm-plan-card.yaml")
    assert "### 🗓️ ATFM plan YSSY, Wed 18 Nov" in sydney
    assert "Version 1" in sydney
    assert "⏳" not in sydney
    assert "| 06:00 | 34 DVAB | 34 |" in sydney
    assert "| ▶ **13:00** | **34 DVAA** | **44** |" in sydney
    assert "| 22:00 | 34 DVAB | 32 |" in sydney

    perth = render(hass, "atfm-plan-card.yaml", "ypph")
    assert "⏳ **Ground delay program:**\nGDP-A 11:00–01:00, 208 flights" in perth
    assert "GDP-A 11:00–01:00, 208 flights affected, average delay 8.9 min" in perth

    alice = render(hass, "atfm-plan-card.yaml", "ybas")
    assert "No ATFM Daily Plan" in alice
