import asyncio
import requests
import re
import html
from datetime import datetime, timezone
from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback


def fetch_atis_data(airport_code: str):
    """Fetch ATIS data for a given airport code."""
    url = f"http://aussieadsb.com/airportinfo/{airport_code}"
    try:
        r = requests.get(url, timeout=10)
        r.raise_for_status()
        html_text = r.text
    except Exception as e:
        return {"state": f"Error: {e}", "attributes": {}}

    # Extract ATIS block
    atis_match = re.search(r"<h6>ATIS</h6>.*?<p class=\"monospace\">(.*?)</p>", html_text, re.DOTALL)
    atis_raw = atis_match.group(1) if atis_match else None

    if atis_raw:
        # Decode HTML entities and normalize
        atis_text = html.unescape(atis_raw)
        # Replace newlines encoded as &#xA;
        atis_text = atis_text.replace("&#xA;", "\n")
        # Remove leading '+' and normalize indentation
        atis_lines = []
        for line in atis_text.splitlines():
            line = line.strip()
            if line.startswith("+"):
                line = line[1:].strip()
            atis_lines.append(line)
        atis_text = "\n".join(atis_lines)
    else:
        atis_text = "No ATIS available"

    # Extract ATIS code
    code_match = re.search(r"ATIS .* (\w)\s+", atis_text)
    atis_code = code_match.group(1) if code_match else None

    # Extract METAR and TAF
    metar_match = re.search(r"<h6>METAR/SPECI</h6>.*?<p class=\"monospace\">(.*?)</p>", html_text, re.DOTALL)
    metar = html.unescape(metar_match.group(1)).replace("&#xA;", "\n").strip() if metar_match else None

    taf_match = re.search(r"<h6>TAF</h6>.*?<p class=\"monospace\">(.*?)</p>", html_text, re.DOTALL)
    taf = html.unescape(taf_match.group(1)).replace("&#xA;", "\n").strip() if taf_match else None

    return {
        # Use ATIS code as the state (or "unknown" if missing)
        "state": atis_code or "unknown",
        "attributes": {
            "atis": atis_text,              # Full ATIS block
            "code": atis_code,              # ATIS code
            "metar": metar,
            "taf": taf,
            "last_updated": datetime.now(timezone.utc).isoformat(),
        }
    }


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback):
    """Set up ATIS sensors from a config entry."""
    airports = entry.data.get("airports", [])
    sensors = [ATISFullSensor(code) for code in airports]
    async_add_entities(sensors, update_before_add=True)


class ATISFullSensor(SensorEntity):
    """Sensor that holds ATIS code as state and full ATIS as attribute."""

    def __init__(self, airport_code: str):
        self.airport_code = airport_code
        self._data = {"state": "unknown", "attributes": {}}
        self._attr_name = f"ATIS {self.airport_code}"

    @property
    def name(self):
        return self._attr_name

    @property
    def state(self):
        """Use ATIS code as the state."""
        return self._data.get("state", "unknown")

    @property
    def extra_state_attributes(self):
        """Include full ATIS block as attribute."""
        return self._data.get("attributes", {})

    async def async_update(self):
        """Fetch the latest ATIS data asynchronously."""
        loop = asyncio.get_event_loop()
        self._data = await loop.run_in_executor(None, fetch_atis_data, self.airport_code)
