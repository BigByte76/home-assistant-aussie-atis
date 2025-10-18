"""Sensor for Australian ATIS"""
import logging
from datetime import datetime, timezone
import requests
import re

import voluptuous as vol
from homeassistant.components.sensor import PLATFORM_SCHEMA, SensorEntity
from homeassistant.const import CONF_NAME
import homeassistant.helpers.config_validation as cv

_LOGGER = logging.getLogger(__name__)

CONF_AIRPORT = "airport_code"

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_AIRPORT): cv.string,
    vol.Optional(CONF_NAME, default="Australian ATIS"): cv.string
})

def setup_platform(hass, config, add_entities, discovery_info=None):
    airport = config[CONF_AIRPORT]
    name = config.get(CONF_NAME)
    add_entities([AustralianATISSensor(name, airport)], True)

class AustralianATISSensor(SensorEntity):
    """Representation of an ATIS sensor"""

    def __init__(self, name, airport):
        self._name = name
        self._airport = airport
        self._state = None
        self._attributes = {}

    @property
    def name(self):
        return self._name

    @property
    def state(self):
        return self._state

    @property
    def extra_state_attributes(self):
        return self._attributes

    def update(self):
        """Fetch ATIS info"""
        url = f"http://aussieadsb.com/airportinfo/{self._airport}"
        try:
            r = requests.get(url, timeout=10)
            r.raise_for_status()
            html = r.text
        except Exception as e:
            _LOGGER.error("Error fetching ATIS for %s: %s", self._airport, e)
            return

        # --- ATIS ---
        atis_match = re.search(r"<h6>ATIS</h6>.*?<p class=\"monospace\">(.*?)</p>", html, re.DOTALL)
        atis_raw = atis_match.group(1).replace("&#xA;", "\n").strip() if atis_match else ""

        # --- Approach ---
        approach_match = re.search(r"APCH: (.*?)\n", atis_raw)
        approach = approach_match.group(1).strip() if approach_match else None

        # --- Runways ---
        rwy_arr_match = re.search(r"RWY: (\d+) FOR ARR", atis_raw)
        runway_arr = rwy_arr_match.group(1) if rwy_arr_match else None

        rwy_dep_match = re.search(r"RWY (\d+) FOR DEP", atis_raw)
        runway_dep = rwy_dep_match.group(1) if rwy_dep_match else None

        # --- OPR INFO ---
        opr_lines = []
        collect = False
        for line in atis_raw.splitlines():
            line = line.strip()
            if line.startswith("OPR INFO:"):
                opr_lines.append(line.replace("OPR INFO:", "").strip())
                collect = True
                continue
            if collect:
                if any(line.startswith(k) for k in ["WND:", "WX:", "TMP:", "QNH:"]):
                    collect = False
                else:
                    opr_lines.append(line.strip())
        opr_info = " ".join(opr_lines)

        # --- Wind ---
        wind_match = re.search(r'WND:\s*(.+)', atis_raw)
        wind = wind_match.group(1).strip() if wind_match else None
        wind_dir, wind_speed, wind_max_tw = None, None, None
        if wind:
            m = re.match(r"(VRB|\d{3})/(\d+)(?:.*MAX TW (\d+))?", wind)
            if m:
                wind_dir, wind_speed, wind_max_tw = m.groups()

        # --- Weather ---
        weather_match = re.search(r"WX: (\S+)", atis_raw)
        weather = weather_match.group(1) if weather_match else None

        # --- Temperature ---
        tmp_match = re.search(r"TMP: (\d+)", atis_raw)
        temperature = tmp_match.group(1) if tmp_match else None

        # --- QNH ---
        qnh_match = re.search(r"QNH: (\d+)", atis_raw)
        qnh = qnh_match.group(1) if qnh_match else None

        # --- METAR ---
        metar_match = re.search(r"<h6>METAR/SPECI</h6>.*?<p class=\"monospace\">(.*?)</p>", html, re.DOTALL)
        metar = metar_match.group(1).strip() if metar_match else None

        # --- TAF ---
        taf_match = re.search(r"<h6>TAF</h6>.*?<p class=\"monospace\">(.*?)</p>", html, re.DOTALL)
        taf = taf_match.group(1).replace("&#xA;", "\n").strip() if taf_match else None

        self._state = f"ATIS {self._airport}"
        self._attributes = {
            "atis": atis_raw,
            "code": self._airport,
            "approach": approach,
            "runway_arr": runway_arr,
            "runway_dep": runway_dep,
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
