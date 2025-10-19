import asyncio
import requests
import re
from datetime import datetime, timezone
from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

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

    # ATIS code
    code_match = re.search(r"ATIS .* (\w)\s+", atis_raw or "")
    atis_code = code_match.group(1) if code_match else None

    # Approach
    approach_match = re.search(r"APCH:\s*(.+)", atis_raw or "")
    approach = approach_match.group(1).strip() if approach_match else None

    # ---- RUNWAYS ----
    rwy_match = re.search(r"RWY:\s*(.+)", atis_raw or "")
    runway_line = rwy_match.group(1).strip() if rwy_match else None

    runway_arr = None
    runway_dep = None

    if runway_line:
        # Split multiple runways by "."
        parts = [p.strip() for p in runway_line.split(".")]
        for part in parts:
            # Arrival runway
            arr_match = re.search(r"(\d{2}[A-Z]?)\s*FOR ARR", part)
            if arr_match:
                runway_arr = arr_match.group(1)
            # Departure runway
            dep_match = re.search(r"(\d{2}[A-Z]?)\s*FOR DEP", part)
            if dep_match:
                runway_dep = dep_match.group(1)

        # If only a single runway is given and no ARR/DEP keywords, assume both
        if not runway_arr and not runway_dep and re.fullmatch(r"\d{2}[A-Z]?", runway_line):
            runway_arr = runway_line
            runway_dep = runway_line


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
    opr_info = " ".join(opr_lines) if opr_lines else None

    # Wind
    wind_match = re.search(r"WND:\s*([\w/0-9., \-]+)", atis_raw or "")
    wind = wind_match.group(1).strip() if wind_match else None
    wind_dir = wind_speed = wind_gust = wind_max_tw = None
    if wind:
        wind_base = re.search(r"(\d{3})/(\d+)(?:-(\d+))?", wind)
        if wind_base:
            wind_dir = wind_base.group(1)
            wind_speed = wind_base.group(2)
            wind_gust = wind_base.group(3)
        max_tw_match = re.search(r"MAX\s+(?:TW|XW)\s*(\d+)", wind)
        if max_tw_match:
            wind_max_tw = max_tw_match.group(1)

    # Weather, Temperature, QNH, SIGWX
    weather_match = re.search(r"WX:\s*(\S+)", atis_raw or "")
    weather = weather_match.group(1) if weather_match else None

    tmp_match = re.search(r"TMP:\s*(\d+)", atis_raw or "")
    temperature = tmp_match.group(1) if tmp_match else None

    qnh_match = re.search(r"QNH:\s*(\d+)", atis_raw or "")
    qnh = qnh_match.group(1) if qnh_match else None

    sigwx_match = re.search(r"SIGWX:\s*(.+)", atis_raw or "")
    sigwx = sigwx_match.group(1).strip() if sigwx_match else None

    # METAR
    metar_match = re.search(r"<h6>METAR/SPECI</h6>.*?<p class=\"monospace\">(.*?)</p>", html, re.DOTALL)
    metar = metar_match.group(1).strip() if metar_match else None

    # TAF
    taf_match = re.search(r"<h6>TAF</h6>.*?<p class=\"monospace\">(.*?)</p>", html, re.DOTALL)
    taf = taf_match.group(1).replace("&#xA;", "\n").strip() if taf_match else None

    return {
        "state": f"ATIS {atis_code}" if atis_code else "unknown",
        "attributes": {
            "atis": atis_raw,
            "code": atis_code,
            "approach": approach,
            "runway_arr": runway_arr,
            "runway_dep": runway_dep,
            "opr_info": opr_info,
            "wind": wind,
            "wind_dir": wind_dir,
            "wind_speed": wind_speed,
            "wind_gust": wind_gust,
            "wind_max_tw": wind_max_tw,
            "weather": weather,
            "temperature": temperature,
            "qnh": qnh,
            "sigwx": sigwx,
            "metar": metar,
            "taf": taf,
            "last_updated": datetime.now(timezone.utc).isoformat()
        }
    }

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback):
    """Set up ATIS sensors for the selected airports."""
    airports = entry.data.get("airports", [])
    sensors = []
    for airport_code in airports:
        atis_data = fetch_atis_data(airport_code)
        sensors.append(ATISSensor(airport_code, atis_data))
    async_add_entities(sensors, update_before_add=True)

class ATISSensor(SensorEntity):
    """Sensor for a single ATIS airport."""

    def __init__(self, airport_code: str, atis_data: dict):
        self.airport_code = airport_code
        self._data = atis_data

    @property
    def name(self):
        return f"ATIS {self.airport_code}"

    @property
    def state(self):
        return self._data.get("state")

    @property
    def extra_state_attributes(self):
        return self._data.get("attributes", {})

    async def async_update(self):
        loop = asyncio.get_event_loop()
        self._data = await loop.run_in_executor(None, fetch_atis_data, self.airport_code)
