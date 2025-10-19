from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.helpers.selector import SelectSelector
from homeassistant.helpers import config_validation as cv
import voluptuous as vol

class AussieAtisConfigFlow(config_entries.ConfigFlow, domain="aussie_atis"):
    """Handle a config flow for Aussie ATIS."""

    VERSION = 1

    def __init__(self):
        """Initialize the flow."""
        self.airports = []

    async def async_step_user(self, user_input=None):
        """Handle the initial step."""
        if user_input is not None:
            self.airports = user_input["airports"]
            return self.async_create_entry(title="Australian ATIS", data={"airports": self.airports})

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({
                vol.Required("airports"): SelectSelector(
                    options=["YMML", "YSSY", "YBBN", "YPPH", "YSCB"],
                    multiple=True
                ),
            }),
        )
