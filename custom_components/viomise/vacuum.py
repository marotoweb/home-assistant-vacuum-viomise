"""
Vacuum entity for the Viomi SE integration.

This file defines the ViomiSEVacuum class, which is the Home Assistant
entity that represents the vacuum cleaner. It communicates with the
ViomiSE device handler (the "brain") to perform actions and report state.
"""
import logging
from datetime import timedelta
from typing import Any, List

import voluptuous as vol
from homeassistant.components.vacuum import (
    StateVacuumEntity,
    VacuumEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback, async_get_current_platform
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
    UpdateFailed,
)

from .const import DOMAIN
from .viomise import ViomiSE, ViomiSEException

_LOGGER = logging.getLogger(__name__)

# Service definitions for custom services
SERVICE_CLEAN_ZONE = "viomi_clean_zone"
SERVICE_CLEAN_POINT = "viomi_clean_point"

ATTR_ZONE_ARRAY = "zone"
ATTR_ZONE_REPEATER = "repeats"
ATTR_POINT = "point"

SERVICE_SCHEMA_CLEAN_ZONE = {
    vol.Required(ATTR_ZONE_ARRAY): vol.All(
        list,
        [
            vol.ExactSequence(
                [vol.Coerce(float), vol.Coerce(float), vol.Coerce(float), vol.Coerce(float)]
            )
        ],
    ),
    vol.Optional(ATTR_ZONE_REPEATER, default=1): vol.All(
        vol.Coerce(int), vol.Clamp(min=1, max=3)
    ),
}

SERVICE_SCHEMA_CLEAN_POINT = {
    vol.Required(ATTR_POINT): vol.All(
        vol.ExactSequence([vol.Coerce(float), vol.Coerce(float)])
    )
}

async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Viomi vacuum cleaner robot platform."""
    device_data = hass.data[DOMAIN][entry.entry_id]
    viomi_device: ViomiSE = device_data["device"]
    scan_interval: timedelta = device_data["scan_interval"]

    coordinator = DataUpdateCoordinator(
        hass,
        _LOGGER,
        name=f"{entry.title} Updater",
        update_method=lambda: viomi_device.update(),
        update_interval=scan_interval,
    )

    # Fetch initial data so we have data when entities subscribe
    await coordinator.async_config_entry_first_refresh()

    vacuum_entity = ViomiSEVacuum(entry, viomi_device, coordinator)
    async_add_entities([vacuum_entity])

    # Register custom services
    platform = async_get_current_platform()
    platform.async_register_entity_service(
        SERVICE_CLEAN_ZONE, SERVICE_SCHEMA_CLEAN_ZONE, "async_clean_zone"
    )
    platform.async_register_entity_service(
        SERVICE_CLEAN_POINT, SERVICE_SCHEMA_CLEAN_POINT, "async_clean_point"
    )

class ViomiSEVacuum(CoordinatorEntity, StateVacuumEntity):
    """Representation of a Viomi SE Vacuum cleaner robot."""

    _attr_has_entity_name = True

    def __init__(
        self,
        entry: ConfigEntry,
        device: ViomiSE,
        coordinator: DataUpdateCoordinator,
    ):
        """Initialize the vacuum handler."""
        super().__init__(coordinator)
        self._device = device
        self._attr_name = None  # Use device name provided by HA
        self._attr_unique_id = entry.unique_id
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, str(self.unique_id))},
            name=entry.title,
            manufacturer="Viomi",
            model="Viomi SE (V-RVCLM21A)",
            sw_version=device._device.info().firmware_version,
        )

    @property
    def state(self) -> str | None:
        """Return the current state of the vacuum."""
        return self._device.get_state()

    @property
    def battery_level(self) -> int | None:
        """Return the battery level of the vacuum cleaner."""
        return self._device.get_battery()

    @property
    def fan_speed(self) -> str | None:
        """Return the fan speed of the vacuum cleaner."""
        return self._device.get_fan_speed()

    @property
    def fan_speed_list(self) -> list[str]:
        """Get the list of available fan speed steps."""
        return self._device.fan_speeds()

    @property
    def supported_features(self) -> VacuumEntityFeature:
        """Flag supported features."""
        return (
            VacuumEntityFeature.STATE
            | VacuumEntityFeature.PAUSE
            | VacuumEntityFeature.STOP
            | VacuumEntityFeature.RETURN_HOME
            | VacuumEntityFeature.BATTERY
            | VacuumEntityFeature.FAN_SPEED
            | VacuumEntityFeature.LOCATE
            | VacuumEntityFeature.SEND_COMMAND
            | VacuumEntityFeature.START
            | VacuumEntityFeature.CLEAN_ZONE
        )

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the specific state attributes of this vacuum cleaner."""
        return self._device.vacuum_state or {}

    # --- Command Methods ---

    async def async_start(self) -> None:
        """Start or resume the cleaning task."""
        await self.hass.async_add_executor_job(self._device.start)
        await self.coordinator.async_refresh()

    async def async_pause(self) -> None:
        """Pause the cleaning task."""
        await self.hass.async_add_executor_job(self._device.pause)
        await self.coordinator.async_refresh()

    async def async_stop(self, **kwargs: Any) -> None:
        """Stop the vacuum cleaner."""
        await self.hass.async_add_executor_job(self._device.stop)
        await self.coordinator.async_refresh()

    async def async_return_to_base(self, **kwargs: Any) -> None:
        """Set the vacuum cleaner to return to the dock."""
        await self.hass.async_add_executor_job(self._device.home)
        await self.coordinator.async_refresh()

    async def async_locate(self, **kwargs: Any) -> None:
        """Locate the vacuum cleaner."""
        await self.hass.async_add_executor_job(self._device.find)

    async def async_set_fan_speed(self, fan_speed: str, **kwargs: Any) -> None:
        """Set fan speed."""
        await self.hass.async_add_executor_job(self._device.set_fan_speed, fan_speed)
        await self.coordinator.async_refresh()

    async def async_send_command(
        self,
        command: str,
        params: dict[str, Any] | list[Any] | None = None,
        **kwargs: Any,
    ) -> None:
        """Send a command to a vacuum cleaner."""
        await self.hass.async_add_executor_job(
            self._device.send_command, command, params
        )
        await self.coordinator.async_refresh()

    async def async_clean_zone(self, zone: list[list[float]], repeats: int = 1) -> None:
        """Clean a zoned area."""
        await self.hass.async_add_executor_job(self._device.clean_zone, zone, repeats)
        await self.coordinator.async_refresh()

    async def async_clean_point(self, point: list[float]) -> None:
        """Clean a specific point."""
        await self.hass.async_add_executor_job(self._device.clean_point, point)
        await self.coordinator.async_refresh()

