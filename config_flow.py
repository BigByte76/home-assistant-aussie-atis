"""Config flow for Australian ATIS integration."""
import voluptuous as vol
from homeassistant import config_entries

DOMAIN = "australian_atis"

class AustralianATISConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Australian ATIS."""

    async def async_step_user(self, user_input=None):
        """Handle the initial step."""
        if user_input is not None:
            return self.async_create_entry(title=user_input["airport"], data=user_input)

        data_schema = vol.Schema({
            vol.Required("airport", default="YMML"): str,
            vol.Optional("refresh_interval", default=1800): int,  # in seconds
        })
        return self.async_show_form(step_id="user", data_schema=data_schema)
