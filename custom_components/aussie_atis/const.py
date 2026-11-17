"""Constants for the Australian ATIS integration."""

from datetime import timedelta
from typing import Final

DOMAIN: Final = "aussie_atis"

CONF_AIRPORTS: Final = "airports"
# Download the ATFM Daily Plan for the airports it covers. Off by default; a
# missing key (entries from before 2.2.0) means off.
CONF_ATFM: Final = "atfm"

BASE_URL: Final = "https://aussieadsb.com/airportinfo/{code}"
ATTRIBUTION: Final = "Data provided by Aussie ADS-B (aussieadsb.com)"
MANUFACTURER: Final = "Aussie ADS-B"

SCAN_INTERVAL: Final = timedelta(minutes=5)
REQUEST_TIMEOUT: Final = 20  # seconds

# ATFM Daily Plan from Airservices Australia, published each evening for the
# next day (and occasionally revised). It is a PDF of about 1 MB.
ATFM_URL: Final = "https://www.airservicesaustralia.com/noc/filex.asp?file=ATFM_Daily_Plan.pdf"
ATFM_ATTRIBUTION: Final = "ATFM Daily Plan provided by Airservices Australia"
ATFM_SCAN_INTERVAL: Final = timedelta(hours=6)
# Retry sooner than the normal interval after a failed download.
ATFM_RETRY_INTERVAL: Final = timedelta(minutes=30)
ATFM_REQUEST_TIMEOUT: Final = 60  # seconds

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
