from homeassistant.core import HomeAssistant

DOMAIN = "aussie_atis"

async def async_setup(hass: HomeAssistant, config: dict):
    """Set up the Aussie ATIS component (empty for config flow)."""
    return True

async def async_setup_entry(hass: HomeAssistant, entry):
    """Set up Aussie ATIS from a config entry."""
    # Store selected airports in hass.data
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = entry.data["airports"]
    return True

async def async_unload_entry(hass, entry):
    """Unload a config entry."""
    hass.data[DOMAIN].pop(entry.entry_id, None)
    return True
