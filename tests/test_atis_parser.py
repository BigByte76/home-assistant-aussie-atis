"""Tests for the ATIS page parser, using pages captured from aussieadsb.com."""

from datetime import UTC, datetime
from pathlib import Path

import pytest

from atis_parser import parse_airport_page, parse_atis, parse_runways, parse_wind

FIXTURES = Path(__file__).parent / "fixtures"
NOW = datetime(2026, 11, 11, 9, 30, tzinfo=UTC)


def load(code: str):
    return parse_airport_page((FIXTURES / f"{code}.html").read_text(), now=NOW)


def test_sydney_parallel_runways_and_multiline_fields() -> None:
    info = load("yssy")
    atis = info.atis
    assert atis is not None
    assert atis.code == "A"
    assert atis.issued == datetime(2026, 11, 11, 9, 13, tzinfo=UTC)
    assert atis.approach == "EXP INDEPENDENT VISUAL APCH. DO NOT PASS THRU ASSIGNED RWY CL"
    assert atis.arrival_runways == ("34L", "34R")
    assert atis.departure_runways == ("34L", "34R")
    assert atis.operational_info is not None
    assert atis.operational_info.endswith("EXP RWY 16L AND R FOR ARR AND DEP")
    # "WIND:" label (not "WND:") with a tailwind component.
    assert (atis.wind_direction, atis.wind_speed, atis.max_tailwind) == (100, 10, 5)
    assert atis.temperature == 21
    assert atis.qnh == 1016
    assert atis.changed_fields == ("operational_info", "wind", "qnh")
    assert info.metar is not None and info.metar.startswith("METAR YSSY")
    assert info.taf is not None and "\n" in info.taf


def test_brisbane_parallel_arrivals_single_departure() -> None:
    atis = load("ybbn").atis
    assert atis is not None
    assert atis.arrival_runways == ("01L", "01R")
    assert atis.departure_runways == ("01R",)
    assert atis.max_crosswind == 18
    assert atis.weather is None  # "+ WX:" with no value
    assert atis.sigwx == "TS IN AREA"
    assert atis.operational_info == (
        "HIGH INTENSITY APPROACH AND HIGH INTENSITY RUNWAY LIGHTING OPERATING. "
        "EXPECT DELAYS ON DEPARTURE. START APPROVAL REQUIRED."
    )


@pytest.mark.parametrize(
    ("code", "arrivals", "departures"),
    [
        ("ymml", ("16",), ("27",)),
        ("ymen", ("26",), ("17",)),
        ("ypad", ("23", "12"), ("23",)),
        ("ypdn", ("11", "36"), ("11", "36")),
        ("ybmk", ("32",), ("32",)),
    ],
)
def test_runway_modes(code: str, arrivals: tuple[str, ...], departures: tuple[str, ...]) -> None:
    atis = load(code).atis
    assert atis is not None
    assert atis.arrival_runways == arrivals
    assert atis.departure_runways == departures


def test_wind_variants() -> None:
    mackay = load("ybmk").atis
    assert mackay is not None
    assert (mackay.max_crosswind, mackay.max_tailwind) == (10, 3)

    essendon = load("ymen").atis
    assert essendon is not None
    assert (essendon.max_crosswind, essendon.max_tailwind) == (16, 2)


def test_unlabelled_lines_go_to_other_info() -> None:
    darwin = load("ypdn").atis
    assert darwin is not None
    assert darwin.other_info == "DEPARTURE FREQUENCY:123.0"
    assert darwin.qnh == 1010

    richmond = load("ysri").atis
    assert richmond is not None
    assert richmond.other_info == "RICHMOND APP FREQ 135.9"
    assert richmond.wind_speed == 8


def test_tower_closed_military_atis() -> None:
    atis = load("yamb").atis
    assert atis is not None
    assert atis.code == "Z"
    assert atis.runway is None
    assert atis.arrival_runways == ()
    assert atis.operational_info == "RWY 04/22 CLOSED FM 0700Z, TACAN NOT AVBL FM 0700Z"
    assert atis.other_info is not None and atis.other_info.startswith("TOWER CLOSED UNTIL 0930Z")


def test_continuation_line_with_change_marker() -> None:
    atis = load("ybok").atis
    assert atis is not None
    assert atis.cloud == "NSC BELOW 5000FT CB TO THE NORTH EAST"
    assert atis.surface_condition is None
    assert atis.operational_info is None


def test_airport_without_atis_still_has_metar_and_taf() -> None:
    info = load("ybas")
    assert info.atis is None
    assert info.metar is not None
    assert info.taf is not None


def test_empty_page() -> None:
    info = parse_airport_page("<html></html>")
    assert (info.atis, info.metar, info.taf) == (None, None, None)


@pytest.mark.parametrize(
    ("text", "arrivals", "departures"),
    [
        ("16L AND R FOR ARRS AND DEPS", ("16L", "16R"), ("16L", "16R")),
        ("34L FOR ARRS, 34R FOR DEPS", ("34L",), ("34R",)),
        ("34L/R", ("34L", "34R"), ("34L", "34R")),
        ("16R FOR ARRS AND DEPS. 16L FOR DEPS ONLY", ("16R",), ("16R", "16L")),
        ("07 AND 34 FOR ARR. 34 FOR DEP", ("07", "34"), ("34",)),
        ("", (), ()),
    ],
)
def test_parse_runways(text: str, arrivals: tuple[str, ...], departures: tuple[str, ...]) -> None:
    assert parse_runways(text) == (arrivals, departures)


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("320/15-25", {"wind_direction": 320, "wind_speed": 15, "wind_gust": 25}),
        ("VRB/5", {"wind_variable": True, "wind_speed": 5}),
        ("CALM", {"wind_speed": 0}),
        ("120/08KT", {"wind_direction": 120, "wind_speed": 8}),
    ],
)
def test_parse_wind(text: str, expected: dict) -> None:
    assert parse_wind(text) == expected


def test_negative_temperature_and_previous_month_stamp() -> None:
    atis = parse_atis("ATIS YMHB Q 302350\nTMP: M2\nQNH: 998", now=datetime(2026, 12, 1, 0, 5, tzinfo=UTC))
    assert atis.temperature == -2
    assert atis.qnh == 998
    assert atis.issued == datetime(2026, 11, 30, 23, 50, tzinfo=UTC)
