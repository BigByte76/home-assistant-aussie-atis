# import logging
import voluptuous as vol
from homeassistant import config_entries
import homeassistant.helpers.config_validation as cv
from .const import DOMAIN, AIRPORTS

_LOGGER = logging.getLogger(__name__)

@config_entries.HANDLERS.register(DOMAIN)
class AussieAtisConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Aussie ATIS."""

    VERSION = 1

    async def async_step_user(self, user_input=None):
        errors = {}
        if user_input is not None:
            return self.async_create_entry(
                title="Aussie ATIS",
                data={"airports": user_input["airports"]}
            )

        schema = vol.Schema({
            vol.Required("airports", default=[]): cv.multi_select(AIRPORTS)
        })

        return self.async_show_form(
            step_id="user",
            data_schema=schema,
            errors=errors
        )
config_flow.py placeholder for multiple airport selection
