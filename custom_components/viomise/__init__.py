# -*- coding: utf-8 -*-
"""The Viomi SE Vacuum integration."""

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_TOKEN, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from miio import Device, DeviceException

from .const import CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL, DOMAIN
from .coordinator import ViomiSECoordinator

_LOGGER = logging.getLogger(__name__)

# Define the platforms that this integration will create entities for.
PLATFORMS: list[Platform] = [Platform.VACUUM, Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Viomi SE from a config entry."""
    if DOMAIN not in hass.data:
        hass.data[DOMAIN] = {}

    host = entry.data[CONF_HOST]
    token = entry.data[CONF_TOKEN]
    scan_interval = entry.options.get(CONF_SCAN_INTERVAL, entry.data.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL))

    try:
        miio_device = Device(host, token)
        device_info = await hass.async_add_executor_job(miio_device.info)
        
        # If the entry doesn't have a unique_id yet (e.g., from older versions), set it now.
        if not entry.unique_id:
            hass.config_entries.async_update_entry(entry, unique_id=device_info.mac_address)

    except DeviceException as e:
        _LOGGER.error("Failed to connect to Viomi SE at %s: %s", host, e)
        raise ConfigEntryNotReady from e

    # Create and configure the data update coordinator.
    coordinator = ViomiSECoordinator(hass, miio_device, scan_interval)
    
    # Fetch initial data so we have it when platforms are set up.
    await coordinator.async_config_entry_first_refresh()

    # Store the coordinator in hass.data for the platforms to access.
    hass.data[DOMAIN][entry.entry_id] = coordinator

    # Forward the setup to the vacuum and sensor platforms.
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)
        _LOGGER.info("Unloaded Viomi SE integration.")
    return unload_ok
