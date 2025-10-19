import requests, re, json
from datetime import datetime, timezone
from homeassistant.helpers.entity import Entity

class AussieAtisSensor(Entity):
    def __init__(self, hass, airport):
        self.hass = hass
        self._airport = airport
        self._attr_name = f"ATIS {airport}"
        self._state = None
        self._attrs = {}

    async def async_added_to_hass(self):
        await self.async_update()

    async def async_update(self):
        url = f"http://aussieadsb.com/airportinfo/{self._airport.lower()}"
        try:
            r = requests.get(url, timeout=10)
            r.raise_for_status()
            html = r.text
        except Exception as e:
            self._state = "unknown"
            self._attrs = {"error": str(e)}
            return

        atis_match = re.search(r"<h6>ATIS</h6>.*?<p class=\"monospace\">(.*?)</p>", html, re.DOTALL)
        atis_raw = atis_match.group(1).replace("&#xA;", "\n").strip() if atis_match else None
        self._attrs["atis_raw"] = atis_raw

        # Extract key data
        def extract(label): return re.search(fr"{label}: (.+)", atis_raw or "")
        self._attrs["approach"] = extract("APCH").group(1) if extract("APCH") else None
        self._attrs["runway"] = extract("RWY").group(1) if extract("RWY") else None
        self._attrs["opr_info"] = extract("OPR INFO").group(1) if extract("OPR INFO") else None
        self._attrs["wind"] = extract("WND").group(1) if extract("WND") else None
        self._attrs["weather"] = extract("WX").group(1) if extract("WX") else None
        self._attrs["temperature"] = extract("TMP").group(1) if extract("TMP") else None
        self._attrs["qnh"] = extract("QNH").group(1) if extract("QNH") else None

        code_match = re.search(r"ATIS .* (\w)\s+", atis_raw or "")
        self._state = f"ATIS {code_match.group(1)}" if code_match else "Active"
        self._attrs["last_updated"] = datetime.now(timezone.utc).isoformat()

    @property
    def name(self):
        return self._attr_name

    @property
    def state(self):
        return self._state

    @property
    def extra_state_attributes(self):
        return self._attrs
