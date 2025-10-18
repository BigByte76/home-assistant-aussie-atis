"""Australian ATIS integration"""
from homeassistant.core import HomeAssistant

DOMAIN = "australian_atis"

async def async_setup_entry(hass: HomeAssistant, entry):
    """Set up from a config entry."""
    hass.async_create_task(
        hass.config_entries.async_forward_entry_setup(entry, "sensor")
    )
    return True

async def async_unload_entry(hass: HomeAssistant, entry):
    """Unload config entry."""
    return await hass.config_entries.async_forward_entry_unload(entry, "sensor")
