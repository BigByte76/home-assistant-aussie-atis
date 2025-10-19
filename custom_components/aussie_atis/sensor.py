import asyncio
import requests
import re
from datetime import datetime, timezone
from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

# Only one sensor per airport (full ATIS)
SENSOR_ATTRIBUTES = [
    "atis",       # full ATIS text (also used as state)
    "code",       # ATIS letter
    "metar",
    "taf",
    "last_updated",
]


def fetch_full_atis(airport_code: str):
    """Fetch page and return the ATIS block and some related fields."""
    url = f"http://aussieadsb.com/airportinfo/{airport_code}"
    try:
        resp = requests.get(url, timeout=10)
        resp.raise_for_status()
        html = resp.text
    except Exception as e:
        return {
            "state": "unknown",
            "attributes": {
                "error": str(e),
                "last_updated": datetime.now(timezone.utc).isoformat(),
            },
        }

    # Extract ATIS block (raw HTML -> replace line breaks encoded as &#xA;)
    atis_match = re.search(r"<h6>ATIS</h6>.*?<p class=\"monospace\">(.*?)</p>", html, re.DOTALL)
    atis_raw = atis_match.group(1).replace("&#xA;", "\n").strip() if atis_match else None

    # Attempt to extract ATIS code letter (if present)
    code_match = re.search(r"ATIS\s+\w+\s+([A-Z])\b", atis_raw or "", re.MULTILINE)
    if not code_match:
        # alternative pattern: ATIS <ICAO> <LETTER> ...
        code_match = re.search(r"ATIS\s+\w+\s+([A-Z])\s+\d{2}", atis_raw or "", re.MULTILINE)
    atis_code = code_match.group(1) if code_match else None

    # METAR
    metar_match = re.search(r"<h6>METAR/SPECI</h6>.*?<p class=\"monospace\">(.*?)</p>", html, re.DOTALL)
    metar = metar_match.group(1).replace("&#xA;", "\n").strip() if metar_match else None

    # TAF
    taf_match = re.search(r"<h6>TAF</h6>.*?<p class=\"monospace\">(.*?)</p>", html, re.DOTALL)
    taf = taf_match.group(1).replace("&#xA;", "\n").strip() if taf_match else None

    attributes = {
        "atis": atis_raw,
        "code": atis_code,
        "metar": metar,
        "taf": taf,
        "last_updated": datetime.now(timezone.utc).isoformat(),
    }

    state = atis_raw if atis_raw else "no atis"

    return {"state": state, "attributes": attributes}


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback):
    """Set up ATIS sensors for the selected airports in the config entry."""
    airports = entry.data.get("airports", [])
    entities = []

    for airport_code in airports:
        entities.append(AtisFullSensor(airport_code))

    async_add_entities(entities, True)


class AtisFullSensor(SensorEntity):
    """Sensor that exposes the full ATIS text as state and meta as attributes."""

    def __init__(self, airport_code: str):
        self.airport_code = airport_code.upper()
        # Friendly name (Home Assistant will create entity_id from this name)
        self._attr_name = f"ATIS {self.airport_code}"
        self._data = {"state": "unknown", "attributes": {"last_updated": None}}

    @property
    def name(self):
        return self._attr_name

    @property
    def state(self):
        return self._data.get("state")

    @property
    def extra_state_attributes(self):
        # Return the parsed attributes dictionary
        return self._data.get("attributes", {})

    async def async_update(self):
        """Update the sensor by fetching ATIS in an executor."""
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(None, fetch_full_atis, self.airport_code)
        # result is dict with keys 'state' and 'attributes'
        self._data = result
