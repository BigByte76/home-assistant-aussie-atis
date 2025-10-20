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
        return {"state": f"Error: {e}", "attributes": {}}

    # Extract ATIS block
    atis_match = re.search(r"<h6>ATIS</h6>.*?<p class=\"monospace\">(.*?)</p>", html, re.DOTALL)
    atis_raw = atis_match.group(1).replace("&#xA;", "\n").strip() if atis_match else None

    # Extract ATIS code
    code_match = re.search(r"ATIS .* (\w)\s+", atis_raw or "")
    atis_code = code_match.group(1) if code_match else None

    # Extract METAR and TAF
    metar_match = re.search(r"<h6>METAR/SPECI</h6>.*?<p class=\"monospace\">(.*?)</p>", html, re.DOTALL)
    metar = metar_match.group(1).strip() if metar_match else None

    taf_match = re.search(r"<h6>TAF</h6>.*?<p class=\"monospace\">(.*?)</p>", html, re.DOTALL)
    taf = taf_match.group(1).replace("&#xA;", "\n").strip() if taf_match else None

    return {
        "state": atis_raw or "No ATIS available",
        "attributes": {
            "code": atis_code,
            "metar": metar,
            "taf": taf,
            "last_updated": datetime.now(timezone.utc).isoformat(),
        }
    }

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback):
    """Set up one ATIS sensor per airport."""
    airports = entry.data.get("airports", [])
    sensors = [ATISFullSensor(code) for code in airports]
    async_add_entities(sensors, update_before_add=True)

class ATISFullSensor(SensorEntity):
    """Sensor that holds full ATIS text as state."""

    def __init__(self, airport_code: str):
        self.airport_code = airport_code
        self._data = {"state": "unknown", "attributes": {}}
        self._attr_name = f"ATIS {self.airport_code}"

    @property
    def name(self):
        return self._attr_name

    @property
    def state(self):
        return self._data.get("state", "unknown")

    @property
    def extra_state_attributes(self):
        return self._data.get("attributes", {})

    async def async_update(self):
        loop = asyncio.get_event_loop()
        self._data = await loop.run_in_executor(None, fetch_atis_data, self.airport_code)
