# custom_components/viomise/__init__.py
# -*- coding: utf-8 -*-
"""The Viomi SE Vacuum integration."""
import logging

from miio import DeviceException, ViomiVacuum

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_TOKEN, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady

from .const import DOMAIN
from .coordinator import ViomiSECoordinator

PLATFORMS: list[Platform] = [Platform.VACUUM]
_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Viomi SE from a config entry."""
    hass.data.setdefault(DOMAIN, {})
    host = entry.data[CONF_HOST]
    token = entry.data[CONF_TOKEN]

    try:
        # Use the ViomiVacuum class from your original code
        vacuum = ViomiVacuum(host, token, model="viomi.vacuum.v19")
        # Test the connection
        await hass.async_add_executor_job(vacuum.info)
    except DeviceException as e:
        raise ConfigEntryNotReady(f"Could not connect to the vacuum: {e}") from e

    # Create the coordinator, passing the vacuum instance
    coordinator = ViomiSECoordinator(hass, vacuum, scan_interval=30)
    
    # Fetch initial data
    await coordinator.async_config_entry_first_refresh()

    # Store the coordinator and vacuum instance to be used by the platform
    hass.data[DOMAIN][entry.entry_id] = {
        "coordinator": coordinator,
        "vacuum": vacuum,
    }

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(async_reload_entry))
    return True

async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)
    return unload_ok

async def async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload config entry."""
    await async_unload_entry(hass, entry)
    await async_setup_entry(hass, entry)
