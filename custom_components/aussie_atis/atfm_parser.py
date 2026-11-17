"""Parse the Airservices Australia ATFM Daily Plan PDF.

The plan is published each evening for the next day's operations at the major
airports. Page 1 is a summary (ground delay programs and delay totals), and
each airport has its own page with notes and an hourly table:

    Time (Hour UTC)   171900   172000   ...
    Runway Mode       34 DVAB  34 DVAB  ...
    Rate              34       40       ...
    METCDM Notes      1        1&2      ...

Runway mode cells are often stacked on two lines ("16/27" over "VMCA"), which
plain text extraction scrambles. So the table is rebuilt from the position of
each piece of text: every fragment is put under the nearest time column.

Like ``atis_parser`` this module has no Home Assistant imports, and
``parse_daily_plan`` never raises: anything it can't read is left empty.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, timedelta
import io
import logging
import re

from pypdf import PdfReader

_LOGGER = logging.getLogger(__name__)

# Airport page titles start with the city name, e.g. "SYDNEY - Nil GDP ...".
ATFM_AIRPORTS: dict[str, str] = {
    "YSSY": "SYDNEY",
    "YMML": "MELBOURNE",
    "YBBN": "BRISBANE",
    "YPPH": "PERTH",
}

_PLAN_DATE = re.compile(r"(\d{1,2})\s+([A-Z][a-z]+)\s+(\d{4})")
_VERSION = re.compile(r"ADP Version\s+(\d+)")
_CHANGE_SUMMARY = re.compile(r"Change Summary:\s*(.+)")
_GDP = re.compile(r"\b(GDP-[A-Z0-9]+)\s+(\d{4})\s*-\s*(\d{4})")
_NOTE = re.compile(r"\[(\d+)\]\s*(\d{4})\s*-\s*(\d{4})\s*:\s*")
_HOUR = re.compile(r"\d{6}")
_RUNWAY = re.compile(r"\d{2}[LRC]?(?:/\d{2}[LRC]?)*")
# Summary row: ICAO, planned GDPs, total arr/dep, affected flights,
# total ground delay, average ground delay.
_SUMMARY_ROW = re.compile(
    r"^\*?(Y[A-Z]{3})\*?\s+(.+?)\s+([\d,]+)\s+(\S+)\s+([\d,]+)\s+([\d.]+)\b",
    re.MULTILINE,
)
# Note sections on an airport page, in order, each ending where the next begins.
_SECTIONS = ("METCDM Notes:", "NCC DLM Notes:", "SM Notes:", "GDP Notes", "Tabulated Data")
_MONTHS = {
    name: number
    for number, name in enumerate(
        (
            "January",
            "February",
            "March",
            "April",
            "May",
            "June",
            "July",
            "August",
            "September",
            "October",
            "November",
            "December",
        ),
        start=1,
    )
}


@dataclass(frozen=True)
class PlanHour:
    """One hour of an airport's plan. Times are UTC."""

    start: datetime
    runway_mode: str | None
    runways: tuple[str, ...]
    # The rest of the runway mode after the runways: a met condition (VMC,
    # IMCA, ...) or an airport-specific mode code (DVAA, DEP VMC, ...).
    mode_code: str | None
    # Planned arrivals per hour.
    arrival_rate: int | None
    # Numbers of the METCDM notes that apply to this hour.
    notes: tuple[int, ...] = ()

    @property
    def end(self) -> datetime:
        return self.start + timedelta(hours=1)


@dataclass(frozen=True)
class PlanNote:
    """A numbered note with the UTC period it applies to."""

    number: int | None
    start: datetime | None
    end: datetime | None
    text: str


@dataclass(frozen=True)
class GroundDelayProgram:
    """A planned ground delay program, e.g. GDP-A 0000-1400 UTC."""

    name: str
    start: datetime | None
    end: datetime | None


@dataclass
class AirportPlan:
    """Everything the plan says about one airport."""

    icao: str
    hours: tuple[PlanHour, ...] = ()
    ground_delay_programs: tuple[GroundDelayProgram, ...] = ()
    metcdm_notes: tuple[PlanNote, ...] = ()
    dlm_notes: tuple[PlanNote, ...] = ()
    sm_notes: tuple[PlanNote, ...] = ()
    gdp_notes: str | None = None
    total_movements: int | None = None
    affected_flights: int | None = None
    # Minutes.
    total_ground_delay: int | None = None
    average_ground_delay: float | None = None

    def hour_at(self, when: datetime) -> PlanHour | None:
        """Return the hour covering ``when``, or None outside the plan."""
        for hour in self.hours:
            if hour.start <= when < hour.end:
                return hour
        return None

    def next_change(self, when: datetime, attr: str) -> PlanHour | None:
        """Return the first later hour where ``attr`` differs from now.

        Before the plan starts, this is the first hour of the plan.
        """
        current = self.hour_at(when)
        for hour in self.hours:
            if hour.start <= when:
                continue
            if current is None or getattr(hour, attr) != getattr(current, attr):
                return hour
        return None

    def notes_for(self, hour: PlanHour | None) -> list[PlanNote]:
        """Return the METCDM notes that apply to ``hour``."""
        if hour is None:
            return []
        return [note for note in self.metcdm_notes if note.number in hour.notes]


@dataclass
class DailyPlan:
    """The parsed ATFM Daily Plan."""

    plan_date: date | None = None
    version: int | None = None
    change_summary: str | None = None
    airports: dict[str, AirportPlan] = field(default_factory=dict)


def carry_over_hours(previous: DailyPlan, plan: DailyPlan, now: datetime) -> None:
    """Keep the previous plan's remaining hours that come before the new plan.

    The next day's plan is published in the evening, while the current plan
    still runs until about midnight in the east. Without this, the current
    hour would be unknown from the download until the new plan starts.
    """
    for icao, airport in plan.airports.items():
        if (old := previous.airports.get(icao)) is None:
            continue
        first = airport.hours[0].start if airport.hours else None
        earlier = tuple(
            hour for hour in old.hours if hour.end > now and (first is None or hour.start < first)
        )
        airport.hours = earlier + airport.hours


@dataclass(frozen=True)
class _Fragment:
    x: float
    y: float
    text: str


def parse_daily_plan(data: bytes) -> DailyPlan:
    """Parse the ATFM Daily Plan PDF. Never raises."""
    plan = DailyPlan()
    try:
        reader = PdfReader(io.BytesIO(data))
        pages = list(reader.pages)
    except Exception as err:  # noqa: BLE001 - pypdf raises many error types
        _LOGGER.debug("Unable to read ATFM Daily Plan: %s", err)
        return plan

    summary: dict[str, tuple] = {}
    for index, page in enumerate(pages):
        try:
            fragments = _fragments(page)
        except Exception as err:  # noqa: BLE001
            _LOGGER.debug("Unable to read page %s of the ATFM Daily Plan: %s", index + 1, err)
            continue
        text = _layout_text(fragments)

        if plan.plan_date is None and "ATFM Daily Plan" in text:
            _parse_summary_page(text, plan, summary)
            continue

        icao = _airport_for_page(text)
        if icao is None or icao in plan.airports:
            continue
        try:
            plan.airports[icao] = _parse_airport_page(icao, fragments, text, plan.plan_date)
        except Exception as err:  # noqa: BLE001 - one bad page shouldn't lose the rest
            _LOGGER.debug("Unable to parse the ATFM Daily Plan page for %s: %s", icao, err)

    for icao, (movements, affected, total_delay, average_delay) in summary.items():
        if airport := plan.airports.get(icao):
            airport.total_movements = movements
            airport.affected_flights = affected
            airport.total_ground_delay = total_delay
            airport.average_ground_delay = average_delay
    return plan


def _layout_text(fragments: list[_Fragment]) -> str:
    """Join fragments into lines in reading order: top to bottom, left to right.

    pypdf returns text in the order it was drawn, which on these pages is not
    reading order (an airport page's title comes after its table).
    """
    lines: list[list[_Fragment]] = []
    for frag in sorted(fragments, key=lambda f: -f.y):
        if lines and abs(lines[-1][0].y - frag.y) <= 3:
            lines[-1].append(frag)
        else:
            lines.append([frag])
    return "\n".join(" ".join(f.text for f in sorted(line, key=lambda f: f.x)) for line in lines)


def _fix_text(text: str) -> str:
    """Undo UTF-8 read as Latin-1 (the PDF has "110Â°" for "110°")."""
    return re.sub("Â([ -¿])", r"\1", text)


def _parse_summary_page(text: str, plan: DailyPlan, summary: dict[str, tuple]) -> None:
    title = next((line for line in text.splitlines() if "ATFM Daily Plan" in line), "")
    plan.plan_date = _parse_date(title)
    if match := _VERSION.search(text):
        plan.version = int(match.group(1))
    if match := _CHANGE_SUMMARY.search(text):
        plan.change_summary = match.group(1).strip()
    for match in _SUMMARY_ROW.finditer(text):
        icao = match.group(1)
        if icao in ATFM_AIRPORTS and icao not in summary:
            summary[icao] = (
                _int(match.group(3)),
                _int(match.group(4)),
                _int(match.group(5)),
                _float(match.group(6)),
            )


def _airport_for_page(text: str) -> str | None:
    for line in text.splitlines()[:3]:
        for icao, city in ATFM_AIRPORTS.items():
            if line.upper().startswith(f"{city} -"):
                return icao
    return None


def _parse_airport_page(
    icao: str, fragments: list[_Fragment], text: str, plan_date: date | None
) -> AirportPlan:
    city = ATFM_AIRPORTS[icao]
    title = next(line for line in text.splitlines() if line.upper().startswith(f"{city} -"))
    plan_date = plan_date or _parse_date(title)

    airport = AirportPlan(icao=icao)
    airport.hours = tuple(_parse_table(fragments, plan_date)) if plan_date else ()

    # Anchor HHMM-only times (notes, GDPs) to the plan window.
    if airport.hours:
        window_start = airport.hours[0].start
    elif plan_date:
        window_start = datetime(plan_date.year, plan_date.month, plan_date.day, tzinfo=UTC) - timedelta(
            hours=12
        )
    else:
        window_start = None

    airport.ground_delay_programs = tuple(
        GroundDelayProgram(name, *_period(start, end, window_start))
        for name, start, end in _GDP.findall(title)
    )

    sections = _split_sections(text)
    airport.metcdm_notes = _parse_notes(sections.get("METCDM Notes:", ""), window_start)
    airport.dlm_notes = _parse_notes(sections.get("NCC DLM Notes:", ""), window_start)
    airport.sm_notes = _parse_notes(sections.get("SM Notes:", ""), window_start)
    airport.gdp_notes = _join_lines(sections.get("GDP Notes", "")) or None
    return airport


def _fragments(page) -> list[_Fragment]:
    fragments: list[_Fragment] = []

    def visit(text, cm, tm, font_dict, font_size) -> None:
        if text.strip():
            # Text origin in page space: the text matrix transformed by the CTM.
            x = tm[4] * cm[0] + tm[5] * cm[2] + cm[4]
            y = tm[4] * cm[1] + tm[5] * cm[3] + cm[5]
            fragments.append(_Fragment(x, y, _fix_text(text.strip())))

    page.extract_text(visitor_text=visit)
    return fragments


def _parse_table(fragments: list[_Fragment], plan_date: date) -> list[PlanHour]:
    times = [f for f in fragments if _HOUR.fullmatch(f.text)]
    if not times:
        return []
    # The time row is the y with the most DDHHMM values.
    row_y = Counter(round(f.y) for f in times).most_common(1)[0][0]
    columns = sorted((f for f in times if abs(f.y - row_y) < 3), key=lambda f: f.x)
    xs = [f.x for f in columns]
    pitch = (xs[-1] - xs[0]) / (len(xs) - 1) if len(xs) > 1 else 40.0

    def label_y(label: str) -> float | None:
        # The table labels sit below the time row; "METCDM Notes:" headings above it don't match.
        ys = [f.y for f in fragments if f.text == label and f.y < row_y]
        return max(ys) if ys else None

    def cells(low: float, high: float) -> list[str]:
        out: list[list[_Fragment]] = [[] for _ in xs]
        for frag in fragments:
            if not low < frag.y < high:
                continue
            index = round((frag.x - xs[0]) / pitch)
            offset = frag.x - (xs[0] + index * pitch)
            if 0 <= index < len(xs) and abs(offset) < pitch / 2:
                out[index].append(frag)
        # Top line first, then left to right.
        return [" ".join(f.text for f in sorted(cell, key=lambda f: (-f.y, f.x))) for cell in out]

    rate_y = label_y("Rate")
    notes_y = label_y("METCDM Notes")
    if rate_y is None:
        return []
    modes = cells(rate_y + 4, row_y - 3)
    rates = cells(rate_y - 4, rate_y + 4)
    notes = cells(notes_y - 4, notes_y + 4) if notes_y is not None else [""] * len(xs)

    hours: list[PlanHour] = []
    for column, mode, rate, note in zip(columns, modes, rates, notes, strict=True):
        start = _resolve_ddhhmm(column.text, plan_date)
        if start is None:
            continue
        runways, mode_code = _split_mode(mode)
        hours.append(
            PlanHour(
                start=start,
                runway_mode=mode or None,
                runways=runways,
                mode_code=mode_code,
                arrival_rate=_int(rate),
                notes=tuple(int(n) for n in re.findall(r"\d+", note) if int(n) > 0),
            )
        )
    return hours


def _parse_date(text: str) -> date | None:
    """Find a date like "18 November 2026"."""
    if (match := _PLAN_DATE.search(text)) is None:
        return None
    day, month_name, year = match.groups()
    if (month := _MONTHS.get(month_name)) is None:
        return None
    try:
        return date(int(year), month, int(day))
    except ValueError:
        return None


def _split_mode(mode: str) -> tuple[tuple[str, ...], str | None]:
    """Split "16/27 VMCA" into (("16", "27"), "VMCA")."""
    runways: list[str] = []
    words = mode.split()
    while words and _RUNWAY.fullmatch(words[0]):
        runways.extend(words.pop(0).split("/"))
    return tuple(runways), " ".join(words) or None


def _resolve_ddhhmm(value: str, plan_date: date) -> datetime | None:
    """Turn DDHHMM into a UTC datetime near the plan date (handles month ends)."""
    day, hour, minute = int(value[:2]), int(value[2:4]), int(value[4:])
    for months in (0, -1, 1):
        year, month = plan_date.year, plan_date.month + months
        if month == 0:
            year, month = year - 1, 12
        elif month == 13:
            year, month = year + 1, 1
        try:
            candidate = datetime(year, month, day, hour, minute, tzinfo=UTC)
        except ValueError:
            continue
        if abs((candidate.date() - plan_date).days) <= 3:
            return candidate
    return None


def _period(start: str, end: str, window_start: datetime | None) -> tuple[datetime | None, datetime | None]:
    """Resolve an HHMM-HHMM UTC period to datetimes in the plan window.

    The start is the first such time at or after the window start. Notes use
    inclusive ends such as 1159, which becomes 1200.
    """
    if window_start is None:
        return None, None
    try:
        start_dt = window_start.replace(hour=int(start[:2]), minute=int(start[2:]))
        end_dt = window_start.replace(hour=int(end[:2]) % 24, minute=int(end[2:]))
    except ValueError:
        return None, None
    if start_dt < window_start:
        start_dt += timedelta(days=1)
    if end_dt.minute == 59:
        end_dt += timedelta(minutes=1)
    while end_dt <= start_dt:
        end_dt += timedelta(days=1)
    return start_dt, end_dt


def _split_sections(text: str) -> dict[str, str]:
    sections: dict[str, str] = {}
    positions = sorted((pos, name) for name in _SECTIONS if (pos := text.find(name)) >= 0)
    for (pos, name), (next_pos, _) in zip(positions, [*positions[1:], (len(text), "")], strict=True):
        sections[name] = text[pos + len(name) : next_pos]
    return sections


def _parse_notes(section: str, window_start: datetime | None) -> tuple[PlanNote, ...]:
    text = _join_lines(section)
    matches = list(_NOTE.finditer(text))
    notes: list[PlanNote] = []
    for index, match in enumerate(matches):
        body_end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        body = text[match.end() : body_end].strip()
        start, end = _period(match.group(2), match.group(3), window_start)
        notes.append(PlanNote(int(match.group(1)), start, end, body))
    return tuple(notes)


def _join_lines(text: str) -> str:
    return " ".join(line.strip() for line in text.splitlines() if line.strip())


def _int(value: str) -> int | None:
    try:
        return int(value.replace(",", ""))
    except ValueError:
        return None


def _float(value: str) -> float | None:
    try:
        return float(value.replace(",", ""))
    except ValueError:
        return None
