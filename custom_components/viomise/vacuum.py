"""
Vacuum entity for the Viomi SE integration.
This file defines the ViomiSEVacuum class, which is the Home Assistant
entity that represents the vacuum cleaner. It communicates with the
ViomiSE device handler (the "brain") to perform actions and report state.
"""
import logging
from datetime import timedelta
from typing import Any

import voluptuous as vol
from homeassistant.components.vacuum import (
    StateVacuumEntity,
    VacuumEntityFeature,
    VacuumActivity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback, async_get_current_platform
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
)
from homeassistant.exceptions import ConfigEntryNotReady

from .const import DOMAIN, CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL
from .viomise import ViomiSE, ViomiSEException

_LOGGER = logging.getLogger(__name__)

# Service definitions
SERVICE_CLEAN_ZONE = "viomi_clean_zone"
SERVICE_CLEAN_POINT = "viomi_clean_point"
ATTR_ZONE_ARRAY = "zone"
ATTR_ZONE_REPEATER = "repeats"
ATTR_POINT = "point"

STATE_CODE_TO_ACTIVITY = {
    0: VacuumActivity.IDLE,      # Sleep
    1: VacuumActivity.IDLE,      # Idle
    2: VacuumActivity.PAUSED,    # Paused
    3: VacuumActivity.RETURNING, # Go Charging
    4: VacuumActivity.DOCKED,    # Charging
    5: VacuumActivity.CLEANING,  # Vacuum
    6: VacuumActivity.CLEANING,  # Vacuum & Mop
    7: VacuumActivity.CLEANING   # Mop only
}

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback):
    """Set up the Viomi vacuum cleaner platform."""
    host = entry.data[CONF_HOST]
    token = entry.data[CONF_TOKEN]
    
    # Create the device handler ("brain")
    viomi_device = ViomiSE(host, token)

    # Connect to the device before setting up the coordinator
    # This handles the ConfigEntryNotReady warning correctly
    try:
        await hass.async_add_executor_job(viomi_device.connect)
    except ViomiSEException as ex:
        raise ConfigEntryNotReady(f"Failed to connect to Viomi SE at {host}: {ex}") from ex

    scan_interval = timedelta(seconds=entry.options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL))

    # Create the data update coordinator
    coordinator = DataUpdateCoordinator(
        hass,
        _LOGGER,
        name=f"{entry.title} Updater",
        update_method=viomi_device.update,
        update_interval=scan_interval,
    )

    # Fetch initial data
    await coordinator.async_config_entry_first_refresh()

    vacuum_entity = ViomiSEVacuum(entry, viomi_device, coordinator)
    async_add_entities([vacuum_entity])

    platform = async_get_current_platform()
    platform.async_register_entity_service(SERVICE_CLEAN_ZONE, SERVICE_SCHEMA_CLEAN_ZONE, "async_clean_zone")
    platform.async_register_entity_service(SERVICE_CLEAN_POINT, SERVICE_SCHEMA_CLEAN_POINT, "async_clean_point")


class ViomiSEVacuum(CoordinatorEntity, StateVacuumEntity):
    """Representation of a Viomi SE Vacuum cleaner robot."""

    _attr_has_entity_name = True

    def __init__(self, entry: ConfigEntry, device: ViomiSE, coordinator: DataUpdateCoordinator):
        super().__init__(coordinator)
        self._device = device
        self._attr_name = None
        self._attr_unique_id = entry.unique_id
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, str(self.unique_id))},
            name=entry.title,
            manufacturer="Viomi",
            model=device.info.model if device.info else "Viomi SE",
            sw_version=device.info.firmware_version if device.info else "Unknown",
        )

    # The coordinator now handles availability automatically
    # We no longer need a separate @property for available

    @property
    def state(self) -> str | None:
        """Return the current state of the vacuum, mapped to HA activities."""
        state_code = self._device.get_state()
        if state_code is None:
            return None
        return STATE_CODE_TO_ACTIVITY.get(state_code)

    @property
    def battery_level(self) -> int | None:
        return self._device.get_battery()

    @property
    def fan_speed(self) -> str | None:
        return self._device.get_fan_speed()

    @property
    def fan_speed_list(self) -> list[str]:
        return self._device.fan_speeds()

    @property
    def supported_features(self) -> VacuumEntityFeature:
        return (
            VacuumEntityFeature.STATE | VacuumEntityFeature.PAUSE | VacuumEntityFeature.STOP |
            VacuumEntityFeature.RETURN_HOME | VacuumEntityFeature.BATTERY | VacuumEntityFeature.FAN_SPEED |
            VacuumEntityFeature.LOCATE | VacuumEntityFeature.SEND_COMMAND | VacuumEntityFeature.START |
            VacuumEntityFeature.CLEAN_ZONE
        )

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return self._device.vacuum_state or {}

    # --- Command Methods ---
    # These now call the device handler and then ask the coordinator to refresh
    async def _execute_command(self, command_func, *args):
        """Execute a device command and refresh state."""
        await self.hass.async_add_executor_job(command_func, *args)
        await self.coordinator.async_request_refresh()

    async def async_start(self):
        await self._execute_command(self._device.start)

    async def async_pause(self):
        await self._execute_command(self._device.pause)

    async def async_stop(self, **kwargs: Any):
        await self._execute_command(self._device.stop)

    async def async_return_to_base(self, **kwargs: Any):
        await self._execute_command(self._device.home)

    async def async_locate(self, **kwargs: Any):
        await self._execute_command(self._device.find)

    async def async_set_fan_speed(self, fan_speed: str, **kwargs: Any):
        await self._execute_command(self._device.set_fan_speed, fan_speed)

    async def async_send_command(self, command: str, params: dict | list | None = None, **kwargs: Any):
        await self._execute_command(self._device.send_command, command, params)

    async def async_clean_zone(self, zone: list[list[float]], repeats: int = 1):
        await self._execute_command(self._device.clean_zone, zone, repeats)

    async def async_clean_point(self, point: list[float]):
        await self._execute_command(self._device.clean_point, point)


