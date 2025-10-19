import requests
import re
import json
from datetime import datetime, timezone
from homeassistant.helpers.entity import Entity

from .const import DOMAIN

class AussieAtisSensor(Entity):
    """Sensor representing ATIS data for a single airport."""

    def __init__(self, airport):
        self._airport = airport
        self._state = None
        self._attributes = {}

    @property
    def name(self):
        return f"ATIS {self._airport}"

    @property
    def state(self):
        return self._state

    @property
    def extra_state_attributes(self):
        return self._attributes

    def update(self):
        """Fetch ATIS data from AussieADSB."""
        url = f"http://aussieadsb.com/airportinfo/{self._airport}"
        try:
            r = requests.get(url, timeout=10)
            r.raise_for_status()
            html = r.text
        except Exception as e:
            self._state = "unknown"
            self._attributes = {"error": str(e)}
            return

        atis_match = re.search(r"<h6>ATIS</h6>.*?<p class=\"monospace\">(.*?)</p>", html, re.DOTALL)
        atis_raw = atis_match.group(1).replace("&#xA;", "\n").strip() if atis_match else None
        atis_lines = [line.strip(" +") for line in atis_raw.splitlines()] if atis_raw else []

        # Extract main fields
        code_match = re.search(r"ATIS .* (\w)\s+", atis_raw or "")
        atis_code = code_match.group(1) if code_match else None

        approach_match = re.search(r"APCH:\s*(.+)", atis_raw or "")
        approach = approach_match.group(1).strip() if approach_match else None

        rwy_match = re.search(r"RWY:\s*(.+)", atis_raw or "")
        runway_line = rwy_match.group(1).strip() if rwy_match else None
        runway_arr = runway_dep = runway_line if runway_line else None

        # OPR info
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
            base = re.search(r"(\d{3})/(\d+)(?:-(\d+))?", wind)
            if base:
                wind_dir = base.group(1)
                wind_speed = base.group(2)
                wind_gust = base.group(3)
            max_tw = re.search(r"MAX\s+(?:TW|XW)\s*(\d+)", wind)
            if max_tw:
                wind_max_tw = max_tw.group(1)

        # Weather
        weather_match = re.search(r"WX:\s*(\S+)", atis_raw or "")
        weather = weather_match.group(1) if weather_match else None

        # Temperature
        tmp_match = re.search(r"TMP:\s*(\d+)", atis_raw or "")
        temperature = tmp_match.group(1) if tmp_match else None

        # QNH
        qnh_match = re.search(r"QNH:\s*(\d+)", atis_raw or "")
        qnh = qnh_match.group(1) if qnh_match else None

        # SIGWX
        sigwx_match = re.search(r"SIGWX:\s*(.+)", atis_raw or "")
        sigwx = sigwx_match.group(1).strip() if sigwx_match else None

        self._state = f"ATIS {atis_code}" if atis_code else "unknown"
        self._attributes = {
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
            "last_updated": datetime.now(timezone.utc).isoformat()
        }
