import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import callback

AIRPORTS = {
    "YSSY": "Sydney Airport",
    "YMML": "Melbourne Airport",
    "YBBN": "Brisbane Airport",
    "YPPH": "Perth Airport",
    "YPAD": "Adelaide Airport",
    "YBCG": "Gold Coast Airport",
    "YBCS": "Cairns Airport",
    "YSCB": "Canberra Airport",
    "YMHB": "Hobart Airport",
    "YPDN": "Darwin International Airport",
    "YBTL": "Townsville Airport",
    "YMLT": "Launceston Airport",
    "YWLM": "RAAF Williamtown/Newcastle Airport",
    "YBMK": "Mackay Airport",
    "YBSU": "Sunshine Coast Airport",
    "YPKA": "Karratha Airport",
    "YBRK": "Rockhampton Airport",
    "YBAS": "Alice Springs Airport",
    "YPPD": "Port Hedland International Airport",
    "YAMB": "RAAF Amberley",
    "YPED": "RAAF Edinburgh",
    "YPTN": "RAAF Tindal",
    "YMES": "RAAF East Sale",
    "YPEA": "RAAF Pearce",
    "YSRI": "RAAF Richmond",
    "YPDN": "RAAF Darwin",
    "YBSG": "RAAF Scherger",
    "YPLM": "RAAF Learmonth",
    "YCIN": "RAAF Curtin",
    "YGIG": "RAAF Gingin",
    "YGNB": "RAAF Glenbrook",
    "YMPC": "RAAF Williams",
    "YPWR": "RAAF Woomera",
    "YBOK": "Oakey Army Aviation Centre",
    "YSNW": "HMAS Albatross"
}

class AussieAtisConfigFlow(config_entries.ConfigFlow, domain="aussie_atis"):
    VERSION = 1

    async def async_step_user(self, user_input=None):
        if user_input is not None:
            return self.async_create_entry(title="Australian ATIS", data=user_input)

        schema = vol.Schema({
            vol.Required("airports", default=["YMML"]): vol.All(cv.ensure_list, [vol.In(AIRPORTS.keys())])
        })
        return self.async_show_form(step_id="user", data_schema=schema)
