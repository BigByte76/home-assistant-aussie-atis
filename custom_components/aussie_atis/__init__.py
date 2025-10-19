from .sensor import AussieAtisSensor
from homeassistant.helpers.entity_platform import AddEntitiesCallback

DOMAIN = "aussie_atis"

async def async_setup(hass, config):
    """Nothing to set up at startup; sensors are created via config entries."""
    return True

async def async_setup_entry(hass, entry, async_add_entities: AddEntitiesCallback):
    """Create ATIS sensors for selected airports."""
    airports = entry.data.get("airports", [])
    entities = [AussieAtisSensor(airport) for airport in airports]
    async_add_entities(entities, update_before_add=True)
    return True
