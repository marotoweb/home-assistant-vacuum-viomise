# custom_components/viomise/__init__.py
# -*- coding: utf-8 -*-
"""The Viomi SE Vacuum integration."""
import logging
import warnings # Importar a biblioteca de avisos

from miio import DeviceException, ViomiVacuum

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_TOKEN, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady

from .const import (
    DOMAIN,
    CONF_COMMAND_COOLDOWN,
    CONF_SCAN_INTERVAL,
    DEFAULT_COMMAND_COOLDOWN,
    DEFAULT_SCAN_INTERVAL,
)
from .coordinator import ViomiSECoordinator

# Suprime o FutureWarning da biblioteca miio, que não podemos controlar.
warnings.filterwarnings("ignore", category=FutureWarning, module=r"miio\.miot_device")

PLATFORMS: list[Platform] = [Platform.VACUUM, Platform.SENSOR]
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

    # Ler os valores das opções, com os defaults como fallback
    cooldown = entry.options.get(CONF_COMMAND_COOLDOWN, DEFAULT_COMMAND_COOLDOWN)
    scan_interval = entry.options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
    
    # Passar o scan_interval para o coordinator
    coordinator = ViomiSECoordinator(hass, vacuum, scan_interval=scan_interval)
    
    await coordinator.async_config_entry_first_refresh()

    # Store the coordinator and vacuum instance to be used by the platform
    hass.data[DOMAIN][entry.entry_id] = {
        "coordinator": coordinator,
        "vacuum": vacuum,
        "cooldown": cooldown,
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
    """Reload config entry when options are updated."""
    await async_unload_entry(hass, entry)
    await async_setup_entry(hass, entry)
