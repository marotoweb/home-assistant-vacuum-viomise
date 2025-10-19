# custom_components/viomise/__init__.py
"""The Viomi SE Vacuum integration."""
import logging
import warnings

from miio import DeviceException, ViomiVacuum

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_TOKEN, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady

from .const import (
    CONF_COMMAND_COOLDOWN,
    CONF_SCAN_INTERVAL,
    DEFAULT_COMMAND_COOLDOWN,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
)
from .coordinator import ViomiSECoordinator

# Suppress a specific FutureWarning from the underlying `miio` library.
# This warning is related to a change in Python 3.13 and is not something
# we can fix in this integration. This keeps the logs clean.
warnings.filterwarnings("ignore", category=FutureWarning, module=r"miio\.miot_device")

# Define the platforms that this integration will set up.
PLATFORMS: list[Platform] = [Platform.VACUUM, Platform.SENSOR]
_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """
    Set up Viomi SE from a config entry.

    This function is called by Home Assistant when the integration is added.
    It sets up the connection, creates the data coordinator, and forwards
    the setup to the platform files (vacuum.py, sensor.py).
    """
    # Ensure the domain data structure exists.
    hass.data.setdefault(DOMAIN, {})
    host = entry.data[CONF_HOST]
    token = entry.data[CONF_TOKEN]

    try:
        # Establish connection to the vacuum.
        vacuum = ViomiVacuum(host, token, model="viomi.vacuum.v19")
        # Perform a quick test to ensure the connection is valid.
        await hass.async_add_executor_job(vacuum.info)
    except DeviceException as e:
        # If connection fails, raise ConfigEntryNotReady to make HA retry later.
        raise ConfigEntryNotReady(f"Could not connect to the vacuum at {host}: {e}") from e

    # Read the configured options, with fallbacks to default values.
    cooldown = entry.options.get(CONF_COMMAND_COOLDOWN, DEFAULT_COMMAND_COOLDOWN)
    scan_interval = entry.options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)

    # Create the DataUpdateCoordinator, which will manage fetching data.
    coordinator = ViomiSECoordinator(hass, vacuum, scan_interval=scan_interval)

    # Fetch initial data from the device before setting up the entities.
    await coordinator.async_config_entry_first_refresh()

    # Store the coordinator, vacuum instance, and options in hass.data for the platforms to use.
    hass.data[DOMAIN][entry.entry_id] = {
        "coordinator": coordinator,
        "vacuum": vacuum,
        "cooldown": cooldown,
    }

    # Forward the setup to the `async_setup_entry` function in each platform file.
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # Add a listener that will reload the integration when its options are changed.
    entry.async_on_unload(entry.add_update_listener(async_reload_entry))

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    # Unload the platforms (vacuum, sensor).
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        # If successful, remove the integration's data from hass.data.
        hass.data[DOMAIN].pop(entry.entry_id)
    return unload_ok


async def async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Handle reloading the config entry when options are updated."""
    await async_unload_entry(hass, entry)
    await async_setup_entry(hass, entry)

