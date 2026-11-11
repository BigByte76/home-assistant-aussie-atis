"""Parse AussieADSB airport info pages into structured ATIS data.

This module deliberately has no Home Assistant imports so it can be unit tested
on its own (see ``tests/``).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
import html
import re

_SECTION_TEMPLATE = r"<h6>\s*{title}\s*</h6>.*?<p class=\"monospace\">(.*?)</p>"

# ATIS header, e.g. "ATIS YSSY A   110913" (ICAO, information letter, DDHHMM UTC).
_HEADER_RE = re.compile(r"^ATIS\s+(?P<icao>[A-Z]{4})\s+(?P<code>[A-Z])\b\s*(?P<time>\d{6})?")

# A labelled ATIS line, e.g. "+ WND: 320/15, MAX XW 18". A leading "+" marks a
# field that changed since the previous information letter.
_FIELD_RE = re.compile(r"^(?P<label>[A-Z][A-Z ]{0,24}?)\s*:\s*(?P<value>.*)$")

# Labels seen across Australian civil and military ATIS, mapped to field names.
_FIELD_ALIASES: dict[str, str] = {
    "APCH": "approach",
    "RWY": "runway",
    "RWYS": "runway",
    "SFC COND": "surface_condition",
    "SFC COND CODE": "surface_condition",
    "SFC CONDITION": "surface_condition",
    "SURFACE COND": "surface_condition",
    "SURFACE CONDITION": "surface_condition",
    "OPR INFO": "operational_info",
    "WND": "wind",
    "WIND": "wind",
    "VIS": "visibility",
    "WX": "weather",
    "PRES WX": "weather",
    "CLD": "cloud",
    "TMP": "temperature",
    "TEMP": "temperature",
    "QNH": "qnh",
    "SIGWX": "sigwx",
    "SIG WX": "sigwx",
    "RMK": "remarks",
}

# Fields that never wrap, so unlabelled lines after them are "other" info
# (e.g. "APP FREQ 126.8" after QNH) rather than a continuation.
_SINGLE_LINE_FIELDS = frozenset({"temperature", "qnh"})

_RUNWAY_TOKEN_RE = re.compile(
    r"\b(?P<num>0[1-9]|[12]\d|3[0-6])(?P<side>[LRC])?\b"  # 34, 34L
    r"|(?:\bAND\b|/)\s*(?P<lone>[LRC])\b"  # the "R" in "34L AND R" or "34L/R"
)
_ARRIVAL_RE = re.compile(r"\b(?:ARR|LDG|LAND)")
_DEPARTURE_RE = re.compile(r"\b(?:DEP|TKOF|TAKE ?OFF)")

_WIND_RE = re.compile(r"\b(?P<dir>\d{3}|VRB)\s*/\s*(?P<speed>\d{1,3})(?:\s*[-G]\s*(?P<gust>\d{1,3}))?")
_CROSSWIND_RE = re.compile(r"\bXW\s*(\d{1,3})")
_TAILWIND_RE = re.compile(r"\bTW\s*(\d{1,3})")
_TEMPERATURE_RE = re.compile(r"^(?P<neg>MS|M|-)?\s*(?P<value>\d{1,2})\b")
_QNH_RE = re.compile(r"\b(\d{3,4})\b")


@dataclass(frozen=True, slots=True)
class AtisReport:
    """A decoded ATIS broadcast."""

    text: str
    code: str | None = None
    issued: datetime | None = None
    approach: str | None = None
    runway: str | None = None
    arrival_runways: tuple[str, ...] = ()
    departure_runways: tuple[str, ...] = ()
    surface_condition: str | None = None
    operational_info: str | None = None
    wind: str | None = None
    wind_direction: int | None = None
    wind_variable: bool = False
    wind_speed: int | None = None
    wind_gust: int | None = None
    max_crosswind: int | None = None
    max_tailwind: int | None = None
    visibility: str | None = None
    weather: str | None = None
    cloud: str | None = None
    temperature: int | None = None
    qnh: int | None = None
    sigwx: str | None = None
    remarks: str | None = None
    other_info: str | None = None
    changed_fields: tuple[str, ...] = field(default=())


@dataclass(frozen=True, slots=True)
class AirportInfo:
    """Everything published for one airport."""

    atis: AtisReport | None
    metar: str | None
    taf: str | None


def parse_airport_page(page: str, now: datetime | None = None) -> AirportInfo:
    """Parse a full AussieADSB ``/airportinfo/<icao>`` HTML page."""
    now = now or datetime.now(UTC)
    atis_text = _section(page, "ATIS")
    return AirportInfo(
        atis=parse_atis(atis_text, now) if atis_text else None,
        metar=_section(page, "METAR/SPECI"),
        taf=_section(page, "TAF"),
    )


def parse_atis(text: str, now: datetime | None = None) -> AtisReport:
    """Parse the plain-text body of an ATIS broadcast."""
    now = now or datetime.now(UTC)
    lines = text.splitlines()

    code: str | None = None
    issued: datetime | None = None
    if lines and (header := _HEADER_RE.match(lines[0])):
        code = header["code"]
        issued = _resolve_ddhhmm(header["time"], now) if header["time"] else None
        lines = lines[1:]

    fields: dict[str, list[str]] = {}
    other: list[str] = []
    changed: list[str] = []
    current: str | None = None

    for raw_line in lines:
        is_changed = raw_line.startswith("+")
        line = raw_line.lstrip("+").strip()
        if not line:
            continue

        match = _FIELD_RE.match(line)
        if match and match["label"].strip() in _FIELD_ALIASES:
            current = _FIELD_ALIASES[match["label"].strip()]
            fields.setdefault(current, [])
            if value := match["value"].strip():
                fields[current].append(value)
            if is_changed and current not in changed:
                changed.append(current)
            if current in _SINGLE_LINE_FIELDS:
                current = None
        elif match:
            # Labelled, but not a standard field (e.g. "DEPARTURE FREQUENCY:123.0").
            current = None
            other.append(line)
        elif current is not None:
            fields[current].append(line)
        else:
            other.append(line)

    values = {name: _clean(" ".join(parts)) for name, parts in fields.items()}
    report: dict[str, object] = {
        name: values.get(name)
        for name in (
            "approach",
            "runway",
            "surface_condition",
            "operational_info",
            "wind",
            "visibility",
            "weather",
            "cloud",
            "sigwx",
            "remarks",
        )
    }

    if runway := values.get("runway"):
        report["arrival_runways"], report["departure_runways"] = parse_runways(runway)
    if wind := values.get("wind"):
        report.update(parse_wind(wind))
    if (temperature := values.get("temperature")) and (m := _TEMPERATURE_RE.match(temperature)):
        report["temperature"] = -int(m["value"]) if m["neg"] else int(m["value"])
    if (qnh := values.get("qnh")) and (m := _QNH_RE.search(qnh)):
        report["qnh"] = int(m[1])

    return AtisReport(
        text=text,
        code=code,
        issued=issued,
        other_info=_clean(" ".join(other)),
        changed_fields=tuple(changed),
        **report,  # type: ignore[arg-type]
    )


def parse_runways(text: str) -> tuple[tuple[str, ...], tuple[str, ...]]:
    """Split a runway field into (arrival, departure) runways.

    Handles parallel runways ("34L AND R FOR ARRS AND DEPS"), split modes
    ("16 FOR ARR. RWY 27 FOR DEP", "01L AND R ARR. 01R DEP") and plain
    runway lists ("11 AND 36"), which are used for both.
    """
    arrivals: list[str] = []
    departures: list[str] = []

    for clause in re.split(r"[.,;]", text.upper()):
        runways: list[str] = []
        last_number: str | None = None
        for token in _RUNWAY_TOKEN_RE.finditer(clause):
            if token["num"]:
                last_number = token["num"]
                runway = last_number + (token["side"] or "")
            elif last_number:
                runway = last_number + token["lone"]
            else:
                continue
            if runway not in runways:
                runways.append(runway)
        if not runways:
            continue

        is_arrival = bool(_ARRIVAL_RE.search(clause))
        is_departure = bool(_DEPARTURE_RE.search(clause))
        if not is_arrival and not is_departure:
            is_arrival = is_departure = True

        for runway in runways:
            if is_arrival and runway not in arrivals:
                arrivals.append(runway)
            if is_departure and runway not in departures:
                departures.append(runway)

    return tuple(arrivals), tuple(departures)


def parse_wind(text: str) -> dict[str, object]:
    """Decode a wind field such as "170/10-20, MAX TW 5 KTS, MAX XW 12"."""
    result: dict[str, object] = {}
    upper = text.upper()
    if match := _WIND_RE.search(upper):
        if match["dir"] == "VRB":
            result["wind_variable"] = True
        else:
            result["wind_direction"] = int(match["dir"])
        result["wind_speed"] = int(match["speed"])
        if match["gust"]:
            result["wind_gust"] = int(match["gust"])
    elif "CALM" in upper:
        result["wind_speed"] = 0
    if crosswinds := _CROSSWIND_RE.findall(upper):
        result["max_crosswind"] = max(int(value) for value in crosswinds)
    if tailwinds := _TAILWIND_RE.findall(upper):
        result["max_tailwind"] = max(int(value) for value in tailwinds)
    return result


def _section(page: str, title: str) -> str | None:
    """Return the decoded monospace text block following an ``<h6>`` heading."""
    match = re.search(_SECTION_TEMPLATE.format(title=re.escape(title)), page, re.DOTALL)
    if not match:
        return None
    lines = [line.strip() for line in html.unescape(match[1]).splitlines()]
    return "\n".join(line for line in lines if line) or None


def _clean(value: str) -> str | None:
    """Collapse whitespace and strip trailing separators; empty becomes None."""
    value = re.sub(r"\s+", " ", value).strip(" ,")
    return value or None


def _resolve_ddhhmm(value: str, now: datetime) -> datetime | None:
    """Turn an ATIS DDHHMM (UTC) stamp into a datetime close to ``now``."""
    day, hour, minute = int(value[:2]), int(value[2:4]), int(value[4:])
    year, month = now.year, now.month
    for _ in range(2):
        try:
            candidate = datetime(year, month, day, hour, minute, tzinfo=UTC)
        except ValueError:
            candidate = None
        # A stamp more than a day in the future belongs to the previous month.
        if candidate is not None and candidate <= now + timedelta(days=1):
            return candidate
        year, month = (year, month - 1) if month > 1 else (year - 1, 12)
    return None
