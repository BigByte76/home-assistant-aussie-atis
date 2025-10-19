import asyncio
import requests
import re
from datetime import datetime, timezone
from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

SENSOR_ATTRIBUTES = [
    "approach",
    "runway_arr",
    "runway_dep",
    "opr_info",
    "wind",
    "wind_dir",
    "wind_speed",
    "wind_gust",
    "wind_max_tw",
    "weather",
    "temperature",
    "qnh",
    "sigwx",
    "metar",
    "taf",
]

def fetch_atis_data(airport_code: str):
    url = f"http://aussieadsb.com/airportinfo/{airport_code}"
    try:
        r = requests.get(url, timeout=10)
        r.raise_for_status()
        html = r.text
    except Exception as e:
        return {"state": "unknown", "attributes": {"error": str(e)}}

    # Extract ATIS block
    atis_match = re.search(r"<h6>ATIS</h6>.*?<p class=\"monospace\">(.*?)</p>", html, re.DOTALL)
    atis_raw = atis_match.group(1).replace("&#xA;", "\n").strip() if atis_match else None
    atis_lines = [line.strip(" +") for line in atis_raw.splitlines()] if atis_raw else []

    # Parse fields
    parsed = {}

    # ATIS code
    code_match = re.search(r"ATIS .* (\w)\s+", atis_raw or "")
    parsed["code"] = code_match.group(1) if code_match else None

    # Approach
    approach_match = re.search(r"APCH:\s*(.+)", atis_raw or "")
    parsed["approach"] = approach_match.group(1).strip() if approach_match else None

    # Runways
    rwy_match = re.search(r"RWY:\s*(.+)", atis_raw or "")
    runway_line = rwy_match.group(1).strip() if rwy_match else None
    parsed["runway_arr"] = parsed["runway_dep"] = None
    if runway_line:
        parts = [p.strip() for p in runway_line.split(".")]
        for part in parts:
            arr_match = re.search(r"(\d{2}[A-Z]?)\s*FOR ARR", part)
            if arr_match:
                parsed["runway_arr"] = arr_match.group(1)
            dep_match = re.search(r"(\d{2}[A-Z]?)\s*FOR DEP", part)
            if dep_match:
                parsed["runway_dep"] = dep_match.group(1)
        # If no explicit ARR/DEP, assign single runway
        if not parsed["runway_arr"] and not parsed["runway_dep"] and re.fullmatch(r"\d{2}[A-Z]?", runway_line):
            parsed["runway_arr"] = parsed["runway_dep"] = runway_line

    # OPR INFO
    opr_lines = []
    collect = False
    for line in atis_lines:
        if line.startswith("OPR INFO:"):
            text = line.replace("OPR INFO:", "").strip()
            if text:
                opr_lines.append(text)
            collect = True
            continue
        if collect:
            if any(line.startswith(k) for k in ["WND:", "WX:", "TMP:", "QNH:", "SIGWX:"]):
                collect = False
            else:
                opr_lines.append(line.strip())
    parsed["opr_info"] = " ".join(opr_lines) if opr_lines else None

    # Wind
    wind_match = re.search(r"WND:\s*([\w/0-9., \-]+)", atis_raw or "")
    wind = wind_match.group(1).strip() if wind_match else None
    parsed["wind"] = wind
    parsed["wind_dir"] = parsed["wind_speed"] = parsed["wind_gust"] = parsed["wind_max_tw"] = None
    if wind:
        base_match = re.search(r"(\d{3})/(\d+)(?:-(\d+))?", wind)
        if base_match:
            parsed["wind_dir"] = base_match.group(1)
            parsed["wind_speed"] = base_match.group(2)
            parsed["wind_gust"] = base_match.group(3)
        max_tw_match = re.search(r"MAX\s+(?:TW|XW)\s*(\d+)", wind)
        if max_tw_match:
            parsed["wind_max_tw"] = max_tw_match.group(1)

    # Other fields
    weather_match = re.search(r"WX:\s*(\S+)", atis_raw or "")
    parsed["weather"] = weather_match.group(1) if weather_match else None

    tmp_match = re.search(r"TMP:\s*(\d+)", atis_raw or "")
    parsed["temperature"] = tmp_match.group(1) if tmp_match else None

    qnh_match = re.search(r"QNH:\s*(\d+)", atis_raw or "")
    parsed["qnh"] = qnh_match.group(1) if qnh_match else None

    sigwx_match = re.search(r"SIGWX:\s*(.+)", atis_raw or "")
    parsed["sigwx"] = sigwx_match.group(1).strip() if sigwx_match else None

    metar_match = re.search(r"<h6>METAR/SPECI</h6>.*?<p class=\"monospace\">(.*?)</p>", html, re.DOTALL)
    parsed["metar"] = metar_match.group(1).strip() if metar_match else None

    taf_match = re.search(r"<h6>TAF</h6>.*?<p class=\"monospace\">(.*?)</p>", html, re.DOTALL)
    parsed["taf"] = taf_match.group(1).replace("&#xA;", "\n").strip() if taf_match else None

    parsed["atis"] = atis_raw
    parsed["last_updated"] = datetime.now(timezone.utc).isoformat()

    return parsed


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback):
    """Set up ATIS sensors for all selected airports and attributes."""
    airports = entry.data.get("airports", [])
    sensors = []

    for airport_code in airports:
        parsed = fetch_atis_data(airport_code)
        for attr in SENSOR_ATTRIBUTES:
            sensors.append(ATISAttributeSensor(airport_code, attr, parsed))

    async_add_entities(sensors, update_before_add=True)


class ATISAttributeSensor(SensorEntity):
    """Sensor for a single ATIS attribute."""

    def __init__(self, airport_code: str, attribute: str, data: dict):
        self.airport_code = airport_code
        self.attribute = attribute
        self._data = data
        self._attr_name = f"{airport_code} ATIS {attribute.replace('_',' ').title()}"

    @property
    def name(self):
        return self._attr_name

    @property
    def state(self):
        return self._data.get(self.attribute, self._data.get("code", "unknown"))

    @property
    def extra_state_attributes(self):
        return self._data

    async def async_update(self):
        loop = asyncio.get_event_loop()
        self._data = await loop.run_in_executor(None, fetch_atis_data, self.airport_code)
