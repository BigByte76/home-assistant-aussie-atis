import logging
from datetime import datetime, timezone
import requests
import re
import json
import voluptuous as vol

import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import Entity
from homeassistant.components.sensor import PLATFORM_SCHEMA

_LOGGER = logging.getLogger(__name__)

CONF_AIRPORT = "airport"

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_AIRPORT): cv.string,
    }
)

def setup_platform(hass, config, add_entities, discovery_info=None):
    airport_code = config[CONF_AIRPORT]
    add_entities([AustralianAtisSensor(airport_code)], True)

class AustralianAtisSensor(Entity):
    def __init__(self, airport):
        self._airport = airport
        self._state = None
        self._attributes = {}

    @property
    def name(self):
        return f"{self._airport} Australian ATIS"

    @property
    def state(self):
        return self._state

    @property
    def extra_state_attributes(self):
        return self._attributes

    def update(self):
        url = f"http://aussieadsb.com/airportinfo/{self._airport}"
        try:
            r = requests.get(url, timeout=10)
            r.raise_for_status()
            html = r.text
        except Exception as e:
            _LOGGER.error("Error fetching ATIS: %s", e)
            return

        atis_match = re.search(r"<h6>ATIS</h6>.*?<p class=\"monospace\">(.*?)</p>", html, re.DOTALL)
        atis_raw = atis_match.group(1).replace("&#xA;", "\n").strip() if atis_match else None

        # --- Parse fields ---
        code_match = re.search(r"ATIS.*?([A-Z])\s", atis_raw or "")
        code = code_match.group(1) if code_match else None

        approach_match = re.search(r"APCH: (.*?)\n", atis_raw or "")
        approach = approach_match.group(1).strip() if approach_match else None

        rwy_arr_match = re.search(r"RWY: (\d+) FOR ARR", atis_raw or "")
        runway_arr = rwy_arr_match.group(1) if rwy_arr_match else None

        rwy_dep_match = re.search(r"RWY (\d+) FOR DEP", atis_raw or "")
        runway_dep = rwy_dep_match.group(1) if rwy_dep_match else None

        opr_lines = []
        collect = False
        for line in atis_raw.splitlines():
            if line.strip().startswith("OPR INFO:"):
                opr_lines.append(line.replace("OPR INFO:", "").strip())
                collect = True
                continue
            if collect:
                if any(line.strip().startswith(k) for k in ["WND:", "WX:", "TMP:", "QNH:"]):
                    collect = False
                else:
                    opr_lines.append(line.strip())
        opr_info = " ".join(opr_lines) if opr_lines else None

        wind_match = re.search(r"WND: (.+)", atis_raw or "")
        wind = wind_match.group(1).strip() if wind_match else None

        # split wind into direction, speed, max TW
        wind_dir = None
        wind_speed = None
        wind_max_tw = None
        if wind:
            parts = re.match(r"([A-Z]+|\d{3})/(\d+)\.?(?: MAX TW (\d+))?", wind)
            if parts:
                wind_dir, wind_speed, wind_max_tw = parts.groups()

        weather_match = re.search(r"WX: (\S+)", atis_raw or "")
        weather = weather_match.group(1) if weather_match else None

        tmp_match = re.search(r"TMP: (\d+)", atis_raw or "")
        temperature = tmp_match.group(1) if tmp_match else None

        qnh_match = re.search(r"QNH: (\d+)", atis_raw or "")
        qnh = qnh_match.group(1) if qnh_match else None

        metar_match = re.search(r"<h6>METAR/SPECI</h6>.*?<p class=\"monospace\">(.*?)</p>", html, re.DOTALL)
        metar = metar_match.group(1).strip() if metar_match else None

        taf_match = re.search(r"<h6>TAF</h6>.*?<p class=\"monospace\">(.*?)</p>", html, re.DOTALL)
        taf = taf_match.group(1).replace("&#xA;", "\n").strip() if taf_match else None

        self._state = f"ATIS {code}" if code else "Unknown"
        self._attributes = {
            "atis": atis_raw,
            "code": code,
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
            "last_updated": datetime.now(timezone.utc).isoformat(),
        }
