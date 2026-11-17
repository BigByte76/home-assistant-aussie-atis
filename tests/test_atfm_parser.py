"""Tests for the ATFM Daily Plan parser, using a plan captured from Airservices.

The fixture is the plan for Wednesday 18 November 2026 with images and the
weather pages removed: the summary page and the four airport pages.
"""

from datetime import UTC, date, datetime
from pathlib import Path

import pytest

from atfm_parser import (
    PlanNote,
    _period,
    _resolve_ddhhmm,
    _split_mode,
    carry_over_hours,
    hours_to_json,
    parse_daily_plan,
    plan_from_hours_json,
)

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture(scope="module")
def plan():
    return parse_daily_plan((FIXTURES / "atfm_daily_plan.pdf").read_bytes())


def utc(day: int, hour: int, minute: int = 0) -> datetime:
    return datetime(2026, 11, day, hour, minute, tzinfo=UTC)


def test_summary(plan) -> None:
    assert plan.plan_date == date(2026, 11, 18)
    assert plan.version == 1
    assert plan.change_summary == "[07:34pm] Version 1: Initial."
    assert set(plan.airports) == {"YSSY", "YMML", "YBBN", "YPPH"}

    sydney = plan.airports["YSSY"]
    assert (sydney.total_movements, sydney.affected_flights) == (827, None)
    assert (sydney.total_ground_delay, sydney.average_ground_delay) == (0, 0.0)
    assert sydney.ground_delay_programs == ()


def test_perth_ground_delay_program(plan) -> None:
    perth = plan.airports["YPPH"]
    assert (perth.total_movements, perth.affected_flights) == (596, 208)
    assert (perth.total_ground_delay, perth.average_ground_delay) == (1852, 8.9)
    [gdp] = perth.ground_delay_programs
    assert (gdp.name, gdp.start, gdp.end) == ("GDP-A", utc(18, 0), utc(18, 14))


def test_sydney_hourly_table(plan) -> None:
    hours = plan.airports["YSSY"].hours
    assert len(hours) == 17
    assert hours[0].start == utc(17, 19)
    assert hours[-1].start == utc(18, 11)
    assert [h.runway_mode for h in hours[4:6]] == ["34 DVAB", "34 DVAA"]
    assert hours[0].runways == ("34",)
    assert hours[0].mode_code == "DVAB"
    assert [h.arrival_rate for h in hours] == [34, 40, 40, 40, 40, *[44] * 9, 38, 38, 32]
    # The stray "0" right of the last column isn't read as a note.
    assert hours[-1].notes == (1,)


def test_melbourne_stacked_runway_mode_cells(plan) -> None:
    melbourne = plan.airports["YMML"]
    hour = melbourne.hour_at(utc(18, 6, 30))
    assert hour is not None
    assert hour.runway_mode == "16/27 VMCA"
    assert hour.runways == ("16", "27")
    assert hour.mode_code == "VMCA"
    assert hour.arrival_rate == 27
    assert melbourne.hours[-1].notes == (3, 4)
    assert [n.number for n in melbourne.notes_for(melbourne.hours[4])] == [1, 2]


def test_brisbane_runway_change_and_notes(plan) -> None:
    brisbane = plan.airports["YBBN"]
    assert brisbane.hours[0].runway_mode == "19 DEP VMC"
    assert brisbane.hours[0].mode_code == "DEP VMC"

    change = brisbane.next_change(utc(17, 20, 30), "runway_mode")
    assert change is not None
    assert (change.start, change.runway_mode) == (utc(18, 1), "01 DEP VMC")
    # Before the plan starts, the next change is the first hour.
    assert brisbane.next_change(utc(17, 12), "runway_mode") is brisbane.hours[0]
    assert brisbane.hour_at(utc(17, 12)) is None
    assert brisbane.hour_at(utc(18, 13)) is None

    note1, note2 = brisbane.metcdm_notes
    assert (note1.start, note1.end) == (utc(17, 20), utc(18, 13))
    assert "110°" in note1.text  # Mojibake "110Â°" repaired.
    assert note1.text.endswith("slight risk of showers 22-01Z.")
    assert note2.text == "SODPROPS expected to be favoured after 11Z."
    assert brisbane.dlm_notes == ()
    assert [(n.number, n.start, n.end) for n in brisbane.sm_notes] == [
        (1, utc(17, 22), utc(18, 2)),
        (2, utc(18, 3), utc(18, 12)),
        (3, utc(18, 12), utc(18, 13)),
    ]
    assert brisbane.sm_notes[0].text.startswith("RWY19L ILS off 2200--0600. Only predicted")
    assert brisbane.gdp_notes == "Nil significant operational issues currently identified."


def test_carry_over_hours_from_previous_plan() -> None:
    previous = parse_daily_plan((FIXTURES / "atfm_daily_plan.pdf").read_bytes())
    plan = parse_daily_plan((FIXTURES / "atfm_daily_plan.pdf").read_bytes())
    # Pretend the new plan starts four hours later, as the next day's would.
    sydney = plan.airports["YSSY"]
    sydney.hours = sydney.hours[4:]

    carry_over_hours(previous, plan, utc(17, 20, 30))
    # 19Z has ended and is dropped; 20-22Z come from the previous plan.
    assert [h.start for h in sydney.hours[:4]] == [utc(17, 20), utc(17, 21), utc(17, 22), utc(17, 23)]
    assert len(sydney.hours) == 16
    assert sydney.hour_at(utc(17, 21, 30)).arrival_rate == 40
    # Same start: nothing to carry over.
    assert len(plan.airports["YMML"].hours) == 18


def test_hours_json_round_trip(plan) -> None:
    data = hours_to_json(plan, utc(18, 1, 30))
    # 19Z to 00Z have ended; 01Z is still running.
    assert data["YSSY"][0]["start"] == "2026-11-18T01:00:00+00:00"
    assert len(data["YSSY"]) == 11

    restored = plan_from_hours_json(data)
    assert set(restored.airports) == {"YSSY", "YMML", "YBBN", "YPPH"}
    for icao, airport in restored.airports.items():
        assert airport.hours == plan.airports[icao].hours[-len(airport.hours) :]
    assert restored.airports["YSSY"].hour_at(utc(18, 1, 30)).runway_mode == "34 DVAA"


def test_hours_json_carries_over_like_the_previous_plan(plan) -> None:
    previous = plan_from_hours_json(hours_to_json(plan, utc(17, 20, 30)))
    new = parse_daily_plan((FIXTURES / "atfm_daily_plan.pdf").read_bytes())
    new.airports["YSSY"].hours = new.airports["YSSY"].hours[4:]
    carry_over_hours(previous, new, utc(17, 20, 30))
    assert [h.start for h in new.airports["YSSY"].hours[:4]] == [
        utc(17, 20),
        utc(17, 21),
        utc(17, 22),
        utc(17, 23),
    ]


def test_carried_hours_keep_their_own_notes() -> None:
    previous = parse_daily_plan((FIXTURES / "atfm_daily_plan.pdf").read_bytes())
    previous.airports["YSSY"].metcdm_notes = (PlanNote(1, None, None, "Today's note."),)
    plan = parse_daily_plan((FIXTURES / "atfm_daily_plan.pdf").read_bytes())
    sydney = plan.airports["YSSY"]
    sydney.hours = sydney.hours[4:]
    new_note = sydney.metcdm_notes[0]
    assert new_note.number == 1

    # Saved and restored, as after a restart.
    carry_over_hours(plan_from_hours_json(hours_to_json(previous, utc(17, 20, 30))), plan, utc(17, 20, 30))
    assert [note.text for note in sydney.notes_for(sydney.hour_at(utc(17, 20, 30)))] == ["Today's note."]
    assert sydney.notes_for(sydney.hour_at(utc(17, 23, 30))) == [new_note]

    # Saved again: the carried hour keeps its note, with its period.
    saved = hours_to_json(plan, utc(17, 20, 30))["YSSY"]
    assert saved[0]["metcdm_notes"] == [{"number": 1, "start": None, "end": None, "text": "Today's note."}]
    assert saved[3]["metcdm_notes"][0]["start"] == new_note.start.isoformat()
    restored = plan_from_hours_json({"YSSY": saved}).airports["YSSY"]
    assert restored.notes_for(restored.hour_at(utc(17, 23, 30))) == [new_note]


@pytest.mark.parametrize(
    "data",
    [
        None,
        [],
        "hours",
        {"YSSY": "34"},
        {"YSSY": [None, {}, {"start": "not a time"}, {"start": "2026-11-18T01:00:00"}, {"start": 5}]},
        {"YSSY": [{"start": "2026-11-18T01:00:00+00:00", "arrival_rate": "many"}]},
        {"YSSY": [{"start": "2026-11-18T01:00:00+00:00", "notes": [None]}]},
        {"YSSY": [{"start": "2026-11-18T01:00:00+00:00", "metcdm_notes": [{"number": 1}]}]},
        {"YSSY": [{"start": "2026-11-18T01:00:00+00:00", "metcdm_notes": [{"text": "x", "start": "soon"}]}]},
    ],
)
def test_bad_hours_json_gives_empty_hours(data) -> None:
    plan = plan_from_hours_json(data)
    assert all(airport.hours == () for airport in plan.airports.values())


def test_unreadable_input_gives_empty_plan() -> None:
    for data in (b"", b"not a pdf", (FIXTURES / "yssy.html").read_bytes()):
        plan = parse_daily_plan(data)
        assert plan.airports == {}
        assert plan.plan_date is None


@pytest.mark.parametrize(
    ("value", "plan_date", "expected"),
    [
        ("171900", date(2026, 11, 18), datetime(2026, 11, 17, 19, tzinfo=UTC)),
        ("311900", date(2026, 11, 1), datetime(2026, 10, 31, 19, tzinfo=UTC)),
        ("010100", date(2026, 12, 31), datetime(2027, 1, 1, 1, tzinfo=UTC)),
        ("101900", date(2026, 11, 18), None),
    ],
)
def test_resolve_ddhhmm(value: str, plan_date: date, expected: datetime | None) -> None:
    assert _resolve_ddhhmm(value, plan_date) == expected


def test_period_wraps_past_midnight() -> None:
    assert _period("2300", "0459", utc(17, 19)) == (utc(17, 23), utc(18, 5))
    assert _period("0000", "1400", utc(17, 22)) == (utc(18, 0), utc(18, 14))
    assert _period("2400", "0100", utc(17, 19)) == (None, None)


@pytest.mark.parametrize(
    ("mode", "runways", "code"),
    [
        ("16/27 VMCA", ("16", "27"), "VMCA"),
        ("34 DVAA", ("34",), "DVAA"),
        ("19 DEP VMC", ("19",), "DEP VMC"),
        ("16L/R", (), "16L/R"),
        ("", (), None),
    ],
)
def test_split_mode(mode: str, runways: tuple[str, ...], code: str | None) -> None:
    assert _split_mode(mode) == (runways, code)
