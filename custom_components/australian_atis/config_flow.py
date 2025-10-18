"""Config flow for Australian ATIS"""
from homeassistant import config_entries
import voluptuous as vol

DOMAIN = "australian_atis"

class AustralianATISConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(self, user_input=None):
        errors = {}
        if user_input is not None:
            return self.async_create_entry(title=user_input["airport_code"], data=user_input)

        data_schema = vol.Schema({
            vol.Required("airport_code", default="YMML"): str
        })
        return self.async_show_form(step_id="user", data_schema=data_schema, errors=errors)
