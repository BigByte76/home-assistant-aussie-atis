from homeassistant import config_entries
from homeassistant.helpers.selector import SelectSelector
import voluptuous as vol

class AussieAtisConfigFlow(config_entries.ConfigFlow, domain="aussie_atis"):
    VERSION = 1

    async def async_step_user(self, user_input=None):
        if user_input is not None:
            airports = user_input["airports"]
            return self.async_create_entry(title="Australian ATIS", data={"airports": airports})

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({
                vol.Required("airports"): SelectSelector(
                    options=["YSSY", "YMML", "YBBN", "YPPH", "YSCB"],
                    multiple=True
                ),
            }),
        )
