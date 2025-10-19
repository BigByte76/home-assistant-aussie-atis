from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.typing import HomeAssistantType

async def async_setup_entry(hass: HomeAssistantType, entry: ConfigEntry):
    """Set up the integration from a config entry."""
    # Forward the setup to the sensor platform
    await hass.config_entries.async_forward_entry_setups(entry, ["sensor"])
    return True
