import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import callback
from .const import DOMAIN

AIRPORTS = [
    "YSSY", "YMML", "YBBN", "YPPH", "YPAD", "YBCG", "YBCS", "YSCB",
    "YMHB", "YPDN", "YBTL", "YMLT", "YWLM", "YBMK", "YBSU", "YPKA",
    "YBRK", "YBAS", "YPPD", "YAMB", "YPED", "YPTN", "YMES", "YPEA",
    "YSRI", "YBTL", "YPDN", "YBSG", "YPLM", "YCIN", "YGIG", "YGNB",
    "YMPC", "YPWR", "YBOK", "YSNW"
]

class AussieAtisConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Aussie ATIS."""

    VERSION = 1

    async def async_step_user(self, user_input=None):
        """Handle the initial step."""
        errors = {}
        if user_input is not None:
            return self.async_create_entry(
                title="Australian ATIS",
                data={
                    "airports": user_input["airports"]
                }
            )

        data_schema = vol.Schema({
            vol.Required("airports", default=["YMML"]): vol.All(
                vol.Length(min=1), vol.Unique(), vol.In(AIRPORTS)
            )
        })

        return self.async_show_form(
            step_id="user",
            data_schema=data_schema,
            errors=errors
        )
