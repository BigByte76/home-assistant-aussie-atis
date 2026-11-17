"""The Australian ATIS integration."""

from __future__ import annotations

from dataclasses import dataclass

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.helpers.storage import Store

from .atfm_parser import ATFM_AIRPORTS
from .const import ATFM_STORE_VERSION, CONF_AIRPORTS, CONF_ATFM, DOMAIN, atfm_store_key
from .coordinator import AtfmCoordinator, AtisCoordinator

PLATFORMS: list[Platform] = [Platform.SENSOR]


@dataclass
class AtisRuntimeData:
    """The coordinators for a config entry."""

    atis: AtisCoordinator
    # Only created when an airport in the ATFM Daily Plan is selected.
    atfm: AtfmCoordinator | None


type AtisConfigEntry = ConfigEntry[AtisRuntimeData]


def get_airports(entry: ConfigEntry) -> list[str]:
    """Return the selected airports (options take precedence over initial data)."""
    return list(entry.options.get(CONF_AIRPORTS, entry.data.get(CONF_AIRPORTS, [])))


def get_atfm_enabled(entry: ConfigEntry) -> bool:
    """Return whether the ATFM Daily Plan is wanted (options take precedence)."""
    return bool(entry.options.get(CONF_ATFM, entry.data.get(CONF_ATFM, False)))


async def async_setup_entry(hass: HomeAssistant, entry: AtisConfigEntry) -> bool:
    """Set up Australian ATIS from a config entry."""
    airports = get_airports(entry)
    coordinator = AtisCoordinator(hass, entry, airports)
    await coordinator.async_config_entry_first_refresh()

    atfm: AtfmCoordinator | None = None
    if get_atfm_enabled(entry) and any(airport in ATFM_AIRPORTS for airport in airports):
        atfm = AtfmCoordinator(hass, entry)
        # The ATFM plan is optional: don't hold up setup or startup for it,
        # and don't fail setup without it. Its entities are unavailable until
        # the first download succeeds.
        entry.async_create_background_task(hass, atfm.async_refresh(), "aussie_atis_atfm_first_refresh")

    entry.runtime_data = AtisRuntimeData(atis=coordinator, atfm=atfm)

    _async_remove_stale_devices(hass, entry, airports)
    if atfm is None:
        _async_remove_atfm_entities(hass, entry)

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(_async_update_listener))
    return True


async def async_unload_entry(hass: HomeAssistant, entry: AtisConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def async_remove_entry(hass: HomeAssistant, entry: AtisConfigEntry) -> None:
    """Delete the saved ATFM hours when the integration is removed."""
    await Store(hass, ATFM_STORE_VERSION, atfm_store_key(entry.entry_id)).async_remove()


async def _async_update_listener(hass: HomeAssistant, entry: AtisConfigEntry) -> None:
    """Reload when the airport selection changes."""
    await hass.config_entries.async_reload(entry.entry_id)


def _async_remove_atfm_entities(hass: HomeAssistant, entry: AtisConfigEntry) -> None:
    """Remove ATFM entities left over from when the ATFM Daily Plan was turned on."""
    entity_registry = er.async_get(hass)
    for entity in er.async_entries_for_config_entry(entity_registry, entry.entry_id):
        # ATFM unique IDs are "{ICAO}_atfm_{field}".
        if "_atfm_" in entity.unique_id:
            entity_registry.async_remove(entity.entity_id)


def _async_remove_stale_devices(hass: HomeAssistant, entry: AtisConfigEntry, airports: list[str]) -> None:
    """Remove devices (and their entities) for airports that were deselected."""
    device_registry = dr.async_get(hass)
    for device in dr.async_entries_for_config_entry(device_registry, entry.entry_id):
        codes = {identifier for domain, identifier in device.identifiers if domain == DOMAIN}
        if codes and codes.isdisjoint(airports):
            device_registry.async_update_device(device.id, remove_config_entry_id=entry.entry_id)
