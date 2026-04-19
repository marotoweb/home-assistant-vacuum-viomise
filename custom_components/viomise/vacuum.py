# custom_components/viomise/vacuum.py
"""Vacuum platform for the Viomi SE integration."""
from __future__ import annotations

import asyncio
import logging
import time
from functools import partial
from typing import Any, Callable

from miio import Device, DeviceException
import voluptuous as vol

from homeassistant.components.vacuum import (
    DOMAIN as VACUUM_DOMAIN,
    StateVacuumEntity,
    VacuumActivity,
    VacuumEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import config_validation as cv, entity_platform
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    CONF_COMMAND_COOLDOWN,
    DEFAULT_COMMAND_COOLDOWN,
    DOMAIN,
)
from .coordinator import ViomiSECoordinator

_LOGGER = logging.getLogger(__name__)

# Fan speeds for the Viomi SE model.
FAN_SPEEDS = {"Silent": 0, "Standard": 1, "Medium": 2, "Turbo": 3}

# Definition of supported features for the vacuum entity.
SUPPORT_XIAOMI = (
    VacuumEntityFeature.STATE
    | VacuumEntityFeature.PAUSE
    | VacuumEntityFeature.STOP
    | VacuumEntityFeature.RETURN_HOME
    | VacuumEntityFeature.FAN_SPEED
    | VacuumEntityFeature.LOCATE
    | VacuumEntityFeature.SEND_COMMAND
    | VacuumEntityFeature.START
)

# Mapping from the device's 'run_state' code to Home Assistant's VacuumActivity enum.
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

# Service definitions for advanced cleaning modes.
SERVICE_CLEAN_ZONE = "xiaomi_clean_zone"
SERVICE_GOTO = "vacuum_goto"
SERVICE_CLEAN_SEGMENT = "vacuum_clean_segment"
SERVICE_CLEAN_POINT = "vacuum_clean_point"
# New service for map management
SERVICE_SET_MAP = "vacuum_set_map"

# Legacy names for backward compatibility with lovelace-xiaomi-vacuum-map-card
LEGACY_CLEAN_ZONE = "xiaomi_clean_zone"
LEGACY_CLEAN_POINT = "xiaomi_clean_point"

ATTR_ZONE_ARRAY = "zone"
ATTR_ZONE_REPEATER = "repeats"
ATTR_X_COORD = "x_coord"
ATTR_Y_COORD = "y_coord"
ATTR_SEGMENTS = "segments"
ATTR_POINT = "point"
ATTR_MAP_ID = "map_id"
ATTR_MAP_NAME = "map_name"
ATTR_MAP_INDEX = "map_index"

# Schemas for the service calls.
SERVICE_SCHEMA_CLEAN_ZONE = {
    vol.Required(ATTR_ZONE_ARRAY): vol.All(list, [vol.ExactSequence([vol.Coerce(float), vol.Coerce(float), vol.Coerce(float), vol.Coerce(float)])]), 
    vol.Optional(ATTR_ZONE_REPEATER, default=1): vol.All(vol.Coerce(int), vol.Clamp(min=1, max=3))
}
SERVICE_SCHEMA_GOTO = {
    vol.Required(ATTR_X_COORD): vol.Coerce(float), 
    vol.Required(ATTR_Y_COORD): vol.Coerce(float)
}
SERVICE_SCHEMA_CLEAN_SEGMENT = {
    vol.Required(ATTR_SEGMENTS): vol.Any(vol.Coerce(int), [vol.Coerce(int)])
}
SERVICE_SCHEMA_CLEAN_POINT = {
    vol.Required(ATTR_POINT): vol.All(vol.ExactSequence([vol.Coerce(float), vol.Coerce(float)]))
}

# Flexible schema: accepts any of the three, but ensures they are the correct type
SERVICE_SCHEMA_SET_MAP = {
    vol.Optional(ATTR_MAP_ID): vol.Coerce(int),
    vol.Optional(ATTR_MAP_NAME): cv.string,
    vol.Optional(ATTR_MAP_INDEX): vol.Coerce(int),
}

# Mapping from service names to the corresponding method.
# Includes both new and legacy names pointing to the same functions.
SERVICE_TO_METHOD = {
    SERVICE_CLEAN_ZONE: {"method": "async_clean_zone", "schema": SERVICE_SCHEMA_CLEAN_ZONE},
    LEGACY_CLEAN_ZONE: {"method": "async_clean_zone", "schema": SERVICE_SCHEMA_CLEAN_ZONE},
    SERVICE_GOTO: {"method": "async_goto", "schema": SERVICE_SCHEMA_GOTO},
    SERVICE_CLEAN_SEGMENT: {"method": "async_clean_segment", "schema": SERVICE_SCHEMA_CLEAN_SEGMENT},
    SERVICE_CLEAN_POINT: {"method": "async_clean_point", "schema": SERVICE_SCHEMA_CLEAN_POINT},
    LEGACY_CLEAN_POINT: {"method": "async_clean_point", "schema": SERVICE_SCHEMA_CLEAN_POINT},
    SERVICE_SET_MAP: {"method": "async_set_map", "schema": SERVICE_SCHEMA_SET_MAP},
}

async def async_setup_entry(hass: HomeAssistant, config_entry: ConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    """Set up the Viomi SE vacuum platform from a config entry."""
    try:
        coordinator = hass.data[DOMAIN][config_entry.entry_id]["coordinator"]
    except KeyError as e:
        _LOGGER.error("Failed to get coordinator from hass.data: %s", e)
        raise ConfigEntryNotReady(f"Coordinator not found for {config_entry.entry_id}") from e
    
    vacuum_entity = MiroboVacuum2(coordinator, config_entry)
    async_add_entities([vacuum_entity])

    # Register custom services for this platform
    # Using entity_platform allows the services to show up in Developer Tools with help text from services.yaml
    platform = entity_platform.async_get_current_platform()

    for service_name, service_info in SERVICE_TO_METHOD.items():
        platform.async_register_entity_service(
            service_name, 
            service_info["schema"], 
            service_info["method"]
        )

class MiroboVacuum2(CoordinatorEntity[ViomiSECoordinator], StateVacuumEntity):
    """Representation of a Viomi SE Robot Vacuum."""
    _attr_has_entity_name = True

    def __init__(self, coordinator: ViomiSECoordinator, config_entry: ConfigEntry) -> None:
        """Initialize the vacuum entity."""
        super().__init__(coordinator)
        self._config_entry = config_entry
        self._vacuum: Device = coordinator.vacuum
        self._attr_name = config_entry.title
        self._attr_unique_id = config_entry.unique_id
        self._last_command_time: float = 0
        self._last_clean_point: list[float] | None = None
        
        # Use dynamic device information from miIO.info
        info = coordinator.device_info_data
        self._attr_device_info = {
            "identifiers": {(DOMAIN, config_entry.unique_id)},
            "name": config_entry.title,
            "manufacturer": "Viomi",
            "model": info.get("model", "Viomi SE (V19)"),
            "sw_version": info.get("fw_ver"),
            "hw_version": info.get("hw_ver"),
        }

    @property
    def supported_features(self) -> VacuumEntityFeature:
        """Flag the supported features."""
        return SUPPORT_XIAOMI

    @property
    def fan_speed_list(self) -> list[str]:
        """Get the list of available fan speed steps."""
        return list(FAN_SPEEDS.keys())

    @property
    def activity(self) -> VacuumActivity | None:
        """Return the current vacuum activity."""
        if not self.coordinator.data or "run_state" not in self.coordinator.data:
            return None
        return STATE_CODE_TO_ACTIVITY.get(self.coordinator.data["run_state"])

    @property
    def fan_speed(self) -> str | None:
        """Return the current fan speed."""
        if not self.coordinator.data or "suction_grade" not in self.coordinator.data:
            return None
        speed_value = self.coordinator.data["suction_grade"]
        for name, value in FAN_SPEEDS.items():
            if value == speed_value:
                return name
        return None

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return the specific state attributes."""
        if not self.coordinator.data:
            return None
        return self.coordinator.data

    async def _try_command(self, command_name: str, mask_error: str, func: Callable, *args: Any, delay: bool = False, skip_cooldown: bool = False, **kwargs: Any) -> bool:
        """Try to call a vacuum command, handling cooldown and exceptions."""
        cooldown = self._config_entry.options.get(CONF_COMMAND_COOLDOWN, DEFAULT_COMMAND_COOLDOWN)
        current_time = time.time()
        if not skip_cooldown and (current_time - self._last_command_time) < cooldown:
            _LOGGER.info("Command '%s' ignored: still cooling down from previous command (cooldown: %.1f s)", command_name, cooldown)
            return False
        self._last_command_time = current_time
        try:
            await self.hass.async_add_executor_job(partial(func, *args, **kwargs))
            if not delay:
                await self.coordinator.async_request_refresh()
            else:
                await asyncio.sleep(1)
            return True
        except DeviceException as exc:
            _LOGGER.error(mask_error, exc)
            return False

    async def async_start(self) -> None:
        """Start or resume the cleaning task."""
        if not self.coordinator.data: return
        mode = self.coordinator.data.get('mode')
        is_mop = self.coordinator.data.get('is_mop')
        actionMode = 0
        if mode == 4 and self._last_clean_point is not None:
            method = 'set_pointclean'
            param = [1, self._last_clean_point[0], self._last_clean_point[1]]
        else:
            if mode == 2: actionMode = 2
            else: actionMode = is_mop if is_mop != 2 else 3
            if mode == 3:
                method = 'set_mode'
                param = [3, 1]
            else:
                method = 'set_mode_withroom'
                param = [actionMode, 1, 0]
        await self._try_command("start", "Unable to start the vacuum: %s", self._vacuum.raw_command, method, param)

    async def async_pause(self) -> None:
        """Pause the cleaning task."""
        if not self.coordinator.data: return
        mode = self.coordinator.data.get('mode')
        is_mop = self.coordinator.data.get('is_mop')
        actionMode = 0
        if mode == 4 and self._last_clean_point is not None:
            method = 'set_pointclean'
            param = [3, self._last_clean_point[0], self._last_clean_point[1]]
        else:
            if mode == 2: actionMode = 2
            else: actionMode = is_mop if is_mop != 2 else 3
            if mode == 3:
                method = 'set_mode'
                param = [3, 3]
            else:
                method = 'set_mode_withroom'
                param = [actionMode, 3, 0]
        await self._try_command("pause", "Unable to set pause: %s", self._vacuum.raw_command, method, param)

    async def async_stop(self, **kwargs: Any) -> None:
        """Stop the vacuum cleaner."""
        if not self.coordinator.data: return
        mode = self.coordinator.data.get('mode')
        if mode == 3:
            method = 'set_mode'
            param = [3, 0]
        elif mode == 4:
            method = 'set_pointclean'
            param = [0, 0, 0]
            self._last_clean_point = None
        else:
            method = 'set_mode'
            param = [0]
        await self._try_command("stop", "Unable to stop: %s", self._vacuum.raw_command, method, param)

    async def async_set_fan_speed(self, fan_speed: str, **kwargs: Any) -> None:
        """Set fan speed."""
        if fan_speed.capitalize() in FAN_SPEEDS:
            speed_value = FAN_SPEEDS[fan_speed.capitalize()]
            await self._try_command("set_fan_speed", "Unable to set fan speed: %s", self._vacuum.raw_command, 'set_suction', [speed_value])
        else:
            _LOGGER.error("Invalid fan speed: %s. Available speeds: %s", fan_speed, self.fan_speed_list)

    async def async_return_to_base(self, **kwargs: Any) -> None:
        """Set the vacuum cleaner to return to the dock."""
        await self._try_command("return_to_base", "Unable to return to base: %s", self._vacuum.raw_command, 'set_charge', [1])

    async def async_locate(self, **kwargs: Any) -> None:
        """Locate the vacuum cleaner."""
        await self._try_command("locate", "Unable to locate the vacuum: %s", self._vacuum.raw_command, 'set_resetpos', [1])

    async def async_send_command(self, command: str, params: dict[str, Any] | list[Any] | None = None, **kwargs: Any) -> None:
        """Send a raw command to the vacuum."""
        if isinstance(params, list) and len(params) == 1 and isinstance(params[0], str):
            if params[0].find('[') > -1 and params[0].find(']') > -1:
                try: params = eval(params[0])
                except Exception: _LOGGER.warning("Invalid eval for params: %s", params)
            elif params[0].isnumeric():
                params[0] = int(params[0])
        await self._try_command("send_command", "Unable to send command to the vacuum: %s", self._vacuum.raw_command, command, params)

    async def async_clean_zone(self, zone: list, repeats: int = 1):
        """Clean selected area(s) for the number of repeats indicated."""

        result = []
        i = 0
        for z in zone:
            x1, y2, x2, y1 = z
            for _ in range(repeats):
                res = '_'.join(str(x) for x in [i, 0, x1, y1, x1, y2, x2, y2, x2, y1])
                result.append(res)
                i += 1
             
        result = [i] + result
        
        if await self._try_command("clean_zone (uploadmap)", "Unable to set uploadmap for zone cleaning", self._vacuum.raw_command, 'set_uploadmap', [1], delay=True):
            if await self._try_command("clean_zone (set_zone)", "Unable to send zone cleaning command", self._vacuum.raw_command, 'set_zone', result, skip_cooldown=True):
                await self._try_command("clean_zone (set_mode)", "Unable to start zone cleaning mode", self._vacuum.raw_command, 'set_mode', [3, 1], skip_cooldown=True)

    async def async_goto(self, x_coord: float, y_coord: float):
        """Go to a specific coordinate."""
        self._last_clean_point = [x_coord, y_coord]
        if await self._try_command("goto (uploadmap)", "Unable to set uploadmap for goto", self._vacuum.raw_command, 'set_uploadmap', [0], delay=True):
            await self._try_command("goto (set_pointclean)", "Unable to go to point", self._vacuum.raw_command, 'set_pointclean', [1, x_coord, y_coord], skip_cooldown=True)

    async def async_clean_segment(self, segments: list[int] | int):
        """Clean selected segment(s) (rooms)."""
        if isinstance(segments, int):
            segments = [segments]
        if await self._try_command("clean_segment (uploadmap)", "Unable to set uploadmap for segment cleaning", self._vacuum.raw_command, 'set_uploadmap', [1], delay=True):
            await self._try_command("clean_segment (set_mode_withroom)", "Unable to clean segments", self._vacuum.raw_command, 'set_mode_withroom', [0, 1, len(segments)] + segments, skip_cooldown=True)

    async def async_clean_point(self, point: list[float]):
        """Clean 2m x 2m area around a specific point."""
        self._last_clean_point = point
        if await self._try_command("clean_point (uploadmap)", "Unable to set uploadmap for point cleaning", self._vacuum.raw_command, 'set_uploadmap', [0], delay=True):
            await self._try_command("clean_point (set_pointclean)", "Unable to clean point", self._vacuum.raw_command, 'set_pointclean', [1, point[0], point[1]], skip_cooldown=True)
    
    async def async_set_map(
            self, 
            map_id: int | None = None, 
            map_name: str | None = None, 
            map_index: int | None = None
        ) -> None:
            """
            Switch the active map using ID, Name, or Index.
            
            This method resolves the target Map ID by fetching the current map list 
            directly from the device if only a Name or Index is provided.
            """
            import json # Import locally to ensure availability in exception blocks
            target_id = map_id

            # If ID is not directly provided, we must resolve it from Name or Index
            if target_id is None:
                _LOGGER.debug(
                    "Resolving map ID for Viomi SE. Criteria: Name='%s', Index=%s", 
                    map_name, map_index
                )
                try:
                    # Fetch the current map list from the device
                    response = await self.hass.async_add_executor_job(
                        self._vacuum.raw_command, "get_map", []
                    )
                    
                    # Extract and parse the nested JSON string from the response
                    # Format: response['out'][0]['value'] -> '[{"name": "...", "id": ...}]'
                    map_data_str = response.get('out', [{}])[0].get('value', '[]')
                    maps = json.loads(map_data_str)

                    if map_name:
                        # Case-insensitive search for the map name
                        target_id = next(
                            (m['id'] for m in maps if m['name'].lower() == map_name.lower()), 
                            None
                        )
                    elif map_index is not None:
                        # Selection by position in the list (0, 1, 2...)
                        if 0 <= map_index < len(maps):
                            target_id = maps[map_index]['id']

                except (KeyError, IndexError, json.JSONDecodeError, TypeError) as err:
                    _LOGGER.error("Failed to parse map list from Viomi SE: %s", err)
                    return
                except Exception as err:
                    _LOGGER.error("Unexpected error during map resolution: %s", err)
                    return

            # Execute the switch command if an ID was successfully resolved
            if target_id is not None:
                _LOGGER.info("Switching Viomi SE to Map ID: %s", target_id)
                # The 'set_map' command expects the ID inside a list [ID]
                await self._try_command(
                    "set_map", 
                    "Failed to switch map: %s", 
                    self._vacuum.raw_command, 
                    'set_map', 
                    [target_id]
                )
            else:
                _LOGGER.error(
                    "Could not resolve map. Criteria: Name=%s, Index=%s, ID=%s", 
                    map_name, map_index, map_id
                )
