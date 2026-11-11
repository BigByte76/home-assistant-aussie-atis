"""The Australian ATIS integration."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from .const import CONF_AIRPORTS, DOMAIN
from .coordinator import AtisCoordinator

PLATFORMS: list[Platform] = [Platform.SENSOR]

type AtisConfigEntry = ConfigEntry[AtisCoordinator]


def get_airports(entry: ConfigEntry) -> list[str]:
    """Return the selected airports (options take precedence over initial data)."""
    return list(entry.options.get(CONF_AIRPORTS, entry.data.get(CONF_AIRPORTS, [])))


async def async_setup_entry(hass: HomeAssistant, entry: AtisConfigEntry) -> bool:
    """Set up Australian ATIS from a config entry."""
    airports = get_airports(entry)
    coordinator = AtisCoordinator(hass, entry, airports)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator

    _async_remove_stale_devices(hass, entry, airports)

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(_async_update_listener))
    return True


async def async_unload_entry(hass: HomeAssistant, entry: AtisConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def _async_update_listener(hass: HomeAssistant, entry: AtisConfigEntry) -> None:
    """Reload when the airport selection changes."""
    await hass.config_entries.async_reload(entry.entry_id)


def _async_remove_stale_devices(hass: HomeAssistant, entry: AtisConfigEntry, airports: list[str]) -> None:
    """Remove devices (and their entities) for airports that were deselected."""
    device_registry = dr.async_get(hass)
    for device in dr.async_entries_for_config_entry(device_registry, entry.entry_id):
        codes = {identifier for domain, identifier in device.identifiers if domain == DOMAIN}
        if codes and codes.isdisjoint(airports):
            device_registry.async_update_device(device.id, remove_config_entry_id=entry.entry_id)
