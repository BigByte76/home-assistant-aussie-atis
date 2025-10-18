"""Australian ATIS sensor platform."""
import logging
import requests
import re
from datetime import datetime, timezone, timedelta
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.event import async_track_time_interval

_LOGGER = logging.getLogger(__name__)

def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the ATIS sensor for each airport entry."""
    if discovery_info is None:
        return

    airport_code = discovery_info.get("airport", "YMML")
    refresh_interval = discovery_info.get("refresh_interval", 300)  # default 5 min
    add_entities([AustralianATISSensor(hass, airport_code, refresh_interval)], True)

class AustralianATISSensor(Entity):
    """Representation of an ATIS sensor."""

    def __init__(self, hass, airport, refresh_interval):
        self._hass = hass
        self._airport = airport
        self._refresh_interval = timedelta(seconds=refresh_interval)
        self._state = None
        self._attributes = {}

        # Schedule periodic updates
        async_track_time_interval(hass, lambda now: self.async_update(), self._refresh_interval)

    @property
    def name(self):
        return f"{self._airport} ATIS"

    @property
    def state(self):
        return self._state

    @property
    def icon(self):
        return "mdi:weather-cloudy"

    @property
    def extra_state_attributes(self):
        return self._attributes

    def update(self):
        """Fetch ATIS data and parse."""
        url = f"http://aussieadsb.com/airportinfo/{self._airport}"
        try:
            response = requests.get(url)
            response.raise_for_status()
            html_content = response.text
        except Exception as e:
            _LOGGER.error("Failed to fetch ATIS for %s: %s", self._airport, e)
            return

        atis_match = re.search(r"<h6>ATIS</h6>.*?<p class=\"monospace\">(.*?)</p>", html_content, re.DOTALL)
        atis_raw = atis_match.group(1).replace("&#xA;", "\n").strip() if atis_match else None

        # --- Parse fields ---
        approach = re.search(r"APCH: (.*?)\n", atis_raw or "")
        approach = approach.group(1).strip() if approach else None

        rwy_arr = re.search(r"RWY: (\d+) FOR ARR", atis_raw or "")
        rwy_arr = rwy_arr.group(1) if rwy_arr else None

        rwy_dep = re.search(r"RWY (\d+) FOR DEP", atis_raw or "")
        rwy_dep = rwy_dep.group(1) if rwy_dep else None

        # --- OPR INFO ---
        opr_lines = []
        collect = False
        if atis_raw:
            for line in atis_raw.splitlines():
                if line.startswith("OPR INFO:"):
                    opr_lines.append(line.replace("OPR INFO:", "").strip())
                    collect = True
                    continue
                if collect:
                    if any(line.startswith(k) for k in ["WND:", "WX:", "TMP:", "QNH:"]):
                        collect = False
                    else:
                        opr_lines.append(line.strip())
        opr_info = " ".join(opr_lines) if opr_lines else None

        # --- Wind ---
        wind_match = re.search(r'WND:\s*(.+)', atis_raw or "")
        wind = wind_match.group(1).strip() if wind_match else None

        wind_dir_match = re.match(r'([A-Z]{2,3}|VRB) (\d+)', wind or "")
        wind_dir = wind_dir_match.group(1) if wind_dir_match else None
        wind_speed = wind_dir_match.group(2) if wind_dir_match else None

        max_tw_match = re.search(r'MAX TW (\d+)', wind or "")
        wind_max_tw = max_tw_match.group(1) if max_tw_match else None

        # --- Weather ---
        weather_match = re.search(r"WX: (\S+)", atis_raw or "")
        weather = weather_match.group(1) if weather_match else None

        # --- Temperature ---
        tmp_match = re.search(r"TMP: (\d+)", atis_raw or "")
        temperature = tmp_match.group(1) if tmp_match else None

        # --- QNH ---
        qnh_match = re.search(r"QNH: (\d+)", atis_raw or "")
        qnh = qnh_match.group(1) if qnh_match else None

        # --- METAR ---
        metar_match = re.search(r"<h6>METAR/SPECI</h6>.*?<p class=\"monospace\">(.*?)</p>", html_content, re.DOTALL)
        metar = metar_match.group(1).strip() if metar_match else None

        # --- TAF ---
        taf_match = re.search(r"<h6>TAF</h6>.*?<p class=\"monospace\">(.*?)</p>", html_content, re.DOTALL)
        taf = taf_match.group(1).replace("&#xA;", "\n").strip() if taf_match else None

        # --- Set state and attributes ---
        self._state = f"ATIS {self._airport}"
        self._attributes = {
            "atis": atis_raw,
            "approach": approach,
            "runway_arr": rwy_arr,
            "runway_dep": rwy_dep,
            "opr_info": opr_info,
            "wind": wind,
            "wind_dir": wind_dir,
            "wind_speed": wind_speed,
            "wind_max_tw": wind_max_tw,
            "weather": weather,
            "temperature": temperature,
            "qnh": qnh,
            "metar": metar,
            "taf": taf,
            "last_updated": datetime.now(timezone.utc).isoformat()
        }
