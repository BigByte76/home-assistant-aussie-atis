"""Constants for the Australian ATIS integration."""

from datetime import timedelta
from typing import Final

DOMAIN: Final = "aussie_atis"

CONF_AIRPORTS: Final = "airports"

BASE_URL: Final = "https://aussieadsb.com/airportinfo/{code}"
ATTRIBUTION: Final = "Data provided by Aussie ADS-B (aussieadsb.com)"
MANUFACTURER: Final = "Aussie ADS-B"

SCAN_INTERVAL: Final = timedelta(minutes=5)
REQUEST_TIMEOUT: Final = 20  # seconds

# Airports offered in the config flow: ICAO code -> display name.
AIRPORTS: Final[dict[str, str]] = {
    # Capital cities
    "YSSY": "Sydney",
    "YMML": "Melbourne",
    "YBBN": "Brisbane",
    "YPPH": "Perth",
    "YPAD": "Adelaide",
    "YSCB": "Canberra",
    "YMHB": "Hobart",
    "YPDN": "Darwin",
    # Major regional / secondary
    "YBCG": "Gold Coast",
    "YBCS": "Cairns",
    "YBTL": "Townsville",
    "YBSU": "Sunshine Coast",
    "YBMK": "Mackay",
    "YBRK": "Rockhampton",
    "YMLT": "Launceston",
    "YMAV": "Avalon",
    "YMEN": "Essendon",
    "YWLM": "Newcastle (Williamtown)",
    "YBAS": "Alice Springs",
    "YPKA": "Karratha",
    "YPPD": "Port Hedland",
    "YPLM": "Learmonth",
    # Military
    "YAMB": "RAAF Base Amberley",
    "YBOK": "Oakey Army Aviation Centre",
    "YCIN": "RAAF Base Curtin",
    "YGIG": "RAAF Gingin",
    "YMES": "RAAF Base East Sale",
    "YMPC": "RAAF Williams Point Cook",
    "YPEA": "RAAF Base Pearce",
    "YPED": "RAAF Base Edinburgh",
    "YPTN": "RAAF Base Tindal",
    "YPWR": "Woomera",
    "YBSG": "RAAF Base Scherger",
    "YSNW": "HMAS Albatross (Nowra)",
    "YSRI": "RAAF Base Richmond",
}
