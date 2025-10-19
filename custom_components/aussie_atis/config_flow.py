from homeassistant import config_entries
import voluptuous as vol
from homeassistant.helpers import selector

AIRPORTS = [
    "YSSY", "YMML", "YBBN", "YPPH", "YPAD", "YBCG", "YBCS",
    "YSCB", "YMHB", "YPDN", "YBTL", "YMLT", "YWLM", "YBMK",
    "YBSU", "YPKA", "YBRK", "YBAS", "YPPD", "YAMB", "YPED",
    "YPTN", "YMES", "YPEA", "YSRI", "YBTL", "YPDN", "YBSG",
    "YPLM", "YCIN", "YGIG", "YGNB", "YMPC", "YPWR", "YBOK", "YSNW"
]

class AussieAtisConfigFlow(config_entries.ConfigFlow, domain="aussie_atis"):
    VERSION = 1

    async def async_step_user(self, user_input=None):
        if user_input is not None:
            return self.async_create_entry(title="Australian ATIS", data=user_input)

        data_schema = vol.Schema({
            vol.Required("airports"): selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=AIRPORTS,
                    multiple=True
                )
            )
        })

        return self.async_show_form(step_id="user", data_schema=data_schema)
