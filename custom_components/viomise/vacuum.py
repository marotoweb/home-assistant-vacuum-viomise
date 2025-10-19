# custom_components/viomise/vacuum.py
"""Vacuum platform for the Viomi SE integration."""
import asyncio
import logging
import time
from functools import partial

import voluptuous as vol
from miio import DeviceException, ViomiVacuum

from homeassistant.components.vacuum import (
    DOMAIN as VACUUM_DOMAIN,
    StateVacuumEntity,
    VacuumActivity,
    VacuumEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import ViomiSECoordinator

_LOGGER = logging.getLogger(__name__)

# --- Constants specific to the vacuum entity ---
FAN_SPEEDS = {"Silent": 0, "Standard": 1, "Medium": 2, "Turbo": 3}
FAN_SPEEDS_REVERSE = {v: k for k, v in FAN_SPEEDS.items()}

SUPPORT_XIAOMI = (
    VacuumEntityFeature.PAUSE | VacuumEntityFeature.STOP | VacuumEntityFeature.RETURN_HOME |
    VacuumEntityFeature.FAN_SPEED | VacuumEntityFeature.LOCATE | VacuumEntityFeature.SEND_COMMAND |
    VacuumEntityFeature.START | VacuumEntityFeature.STATE
)

STATE_CODE_TO_ACTIVITY = {
    0: VacuumActivity.IDLE,      # Idle
    1: VacuumActivity.IDLE,      # Idle
    2: VacuumActivity.PAUSED,    # Paused
    3: VacuumActivity.RETURNING, # Go Charging
    4: VacuumActivity.DOCKED,    # Charging
    5: VacuumActivity.CLEANING,  # Vacuum
    6: VacuumActivity.CLEANING,  # Vacuum & Mop
    7: VacuumActivity.CLEANING   # Mop only
}

# --- Service definitions ---
SERVICE_CLEAN_ZONE = "vacuum_clean_zone"
SERVICE_GOTO = "vacuum_goto"
SERVICE_CLEAN_SEGMENT = "vacuum_clean_segment"
SERVICE_CLEAN_POINT = "xiaomi_clean_point"
ATTR_ZONE_ARRAY = "zone"
ATTR_ZONE_REPEATER = "repeats"
ATTR_X_COORD = "x_coord"
ATTR_Y_COORD = "y_coord"
ATTR_SEGMENTS = "segments"
ATTR_POINT = "point"
VACUUM_SERVICE_SCHEMA = vol.Schema({vol.Optional(ATTR_ENTITY_ID): cv.entity_ids})
SERVICE_SCHEMA_CLEAN_ZONE = VACUUM_SERVICE_SCHEMA.extend({vol.Required(ATTR_ZONE_ARRAY): vol.All(list, [vol.ExactSequence([vol.Coerce(float), vol.Coerce(float), vol.Coerce(float), vol.Coerce(float)])]), vol.Required(ATTR_ZONE_REPEATER): vol.All(vol.Coerce(int), vol.Clamp(min=1, max=3))})
SERVICE_SCHEMA_GOTO = VACUUM_SERVICE_SCHEMA.extend({vol.Required(ATTR_X_COORD): vol.Coerce(float), vol.Required(ATTR_Y_COORD): vol.Coerce(float)})
SERVICE_SCHEMA_CLEAN_SEGMENT = VACUUM_SERVICE_SCHEMA.extend({vol.Required(ATTR_SEGMENTS): vol.Any(vol.Coerce(int), [vol.Coerce(int)])})
SERVICE_SCHEMA_CLEAN_POINT = VACUUM_SERVICE_SCHEMA.extend({vol.Required(ATTR_POINT): vol.All(vol.ExactSequence([vol.Coerce(float), vol.Coerce(float)]))})
SERVICE_TO_METHOD = {SERVICE_CLEAN_ZONE: {"method": "async_clean_zone", "schema": SERVICE_SCHEMA_CLEAN_ZONE}, SERVICE_GOTO: {"method": "async_goto", "schema": SERVICE_SCHEMA_GOTO}, SERVICE_CLEAN_SEGMENT: {"method": "async_clean_segment", "schema": SERVICE_SCHEMA_CLEAN_SEGMENT}, SERVICE_CLEAN_POINT: {"method": "async_clean_point", "schema": SERVICE_SCHEMA_CLEAN_POINT}}


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback):
    """Set up the Viomi vacuum entity from a config entry."""
    # Retrieve the data stored by __init__.py
    integration_data = hass.data[DOMAIN][entry.entry_id]
    coordinator = integration_data["coordinator"]
    cooldown = integration_data["cooldown"]

    # Create the vacuum entity and pass it the coordinator and cooldown value.
    mirobo = MiroboVacuum2(coordinator, entry, cooldown)
    async_add_entities([mirobo], update_before_add=True)

    # Register the custom services for this integration.
    async def async_service_handler(service_call):
        """Handle calls to the custom services."""
        method_def = SERVICE_TO_METHOD.get(service_call.service)
        if not method_def:
            return

        params = {key: value for key, value in service_call.data.items() if key != ATTR_ENTITY_ID}
        entity_ids = service_call.data.get(ATTR_ENTITY_ID)

        # If entity_ids are specified, only act if this vacuum is one of them.
        if entity_ids and mirobo.entity_id not in entity_ids:
            return

        # Call the corresponding method on the vacuum entity instance.
        await getattr(mirobo, method_def["method"])(**params)

    for service, definition in SERVICE_TO_METHOD.items():
        hass.services.async_register(
            VACUUM_DOMAIN,
            service,
            async_service_handler,
            schema=definition.get("schema", VACUUM_SERVICE_SCHEMA),
        )


class MiroboVacuum2(CoordinatorEntity[ViomiSECoordinator], StateVacuumEntity):
    """Representation of a Viomi SE Vacuum cleaner."""
    _attr_has_entity_name = True
    _attr_name = None  # The name will be taken from the device registry.

    def __init__(self, coordinator: ViomiSECoordinator, config_entry: ConfigEntry, command_cooldown: float):
        """Initialize the vacuum entity."""
        super().__init__(coordinator)
        self._vacuum = coordinator.vacuum
        self._attr_unique_id = config_entry.unique_id
        self._last_clean_point = None
        self._attr_device_info = {
            "identifiers": {(DOMAIN, self.unique_id)},
            "name": config_entry.title,
            "manufacturer": "Viomi",
            "model": "V-RVCLM21A (SE)",
        }
        # Store the configurable cooldown and the timestamp of the last command.
        self._command_cooldown = command_cooldown
        self._last_command_time = 0

    @property
    def activity(self) -> VacuumActivity | None:
        """Return the current activity of the vacuum."""
        if self.coordinator.data:
            state_code = self.coordinator.data.get("run_state")
            return STATE_CODE_TO_ACTIVITY.get(state_code)
        return None

    @property
    def fan_speed(self) -> str | None:
        """Return the current fan speed."""
        if self.coordinator.data:
            speed_code = self.coordinator.data.get("suction_grade")
            return FAN_SPEEDS_REVERSE.get(speed_code, speed_code)
        return None

    @property
    def fan_speed_list(self) -> list[str]:
        """Return the list of available fan speeds."""
        return list(sorted(FAN_SPEEDS.keys(), key=lambda s: FAN_SPEEDS[s]))

    @property
    def extra_state_attributes(self) -> dict[str, any] | None:
        """Return device-specific state attributes."""
        return self.coordinator.data

    @property
    def supported_features(self) -> VacuumEntityFeature:
        """Flag the features that this vacuum supports."""
        return SUPPORT_XIAOMI

    async def _try_command(self, mask_error: str, func, *args, **kwargs) -> bool:
        """
        Send a command to the vacuum with a debounce mechanism.

        This prevents flooding the device with too many commands in a short time,
        which can cause errors and timeouts.
        """
        now = time.time()
        if now - self._last_command_time < self._command_cooldown:
            _LOGGER.warning(
                "Command ignored: still cooling down from previous command (cooldown: %s s)",
                self._command_cooldown,
            )
            return False

        self._last_command_time = now

        try:
            # Execute the command in a separate thread to avoid blocking Home Assistant.
            await self.hass.async_add_executor_job(partial(func, *args, **kwargs))
            # After sending a command, request an immediate refresh of the data.
            await self.coordinator.async_request_refresh()
            return True
        except DeviceException as exc:
            _LOGGER.error("%s: %s", mask_error, exc)
            return False

    # --- Standard Vacuum Commands ---

    async def async_start(self):
        """Start or resume cleaning, using the original complex logic."""
        state = self.coordinator.data
        if not state: return
        mode, is_mop = state.get('mode'), state.get('is_mop')
        action_mode = 0
        if mode == 4 and self._last_clean_point:
            method, param = 'set_pointclean', [1, self._last_clean_point[0], self._last_clean_point[1]]
        else:
            if mode == 2: action_mode = 2
            else: action_mode = 3 if is_mop == 2 else is_mop
            if mode == 3: method, param = 'set_mode', [3, 1]
            else: method, param = 'set_mode_withroom', [action_mode, 1, 0]
        await self._try_command("Unable to start", self._vacuum.raw_command, method, param)

    async def async_pause(self):
        """Pause cleaning."""
        state = self.coordinator.data
        if not state: return
        mode, is_mop = state.get('mode'), state.get('is_mop')
        action_mode = 0
        if mode == 4 and self._last_clean_point:
            method, param = 'set_pointclean', [3, self._last_clean_point[0], self._last_clean_point[1]]
        else:
            if mode == 2: action_mode = 2
            else: action_mode = 3 if is_mop == 2 else is_mop
            if mode == 3: method, param = 'set_mode', [3, 3]
            else: method, param = 'set_mode_withroom', [action_mode, 3, 0]
        await self._try_command("Unable to pause", self._vacuum.raw_command, method, param)

    async def async_stop(self, **kwargs):
        """Stop cleaning."""
        state = self.coordinator.data
        if not state: return
        mode = state.get('mode')
        if mode == 3: method, param = 'set_mode', [3, 0]
        elif mode == 4:
            method, param = 'set_pointclean', [0, 0, 0]
            self._last_clean_point = None
        else: method, param = 'set_mode', [0]
        await self._try_command("Unable to stop", self._vacuum.raw_command, method, param)

    async def async_set_fan_speed(self, fan_speed: str, **kwargs):
        """Set the fan speed."""
        speed_value = FAN_SPEEDS.get(fan_speed.capitalize())
        if speed_value is None:
            _LOGGER.error("Invalid fan speed: %s", fan_speed)
            return
        await self._try_command("Unable to set fan speed", self._vacuum.raw_command, 'set_suction', [speed_value])

    async def async_return_to_base(self, **kwargs):
        """Command the vacuum to return to its base."""
        await self._try_command("Unable to return to base", self._vacuum.raw_command, 'set_charge', [1])

    async def async_locate(self, **kwargs):
        """Locate the vacuum by making it emit a sound."""
        await self._try_command("Unable to locate vacuum", self._vacuum.raw_command, 'set_resetpos', [1])

    async def async_send_command(self, command: str, params: dict | list | None = None, **kwargs):
        """Send a raw command to the device."""
        # This handles cases where params come from HA templates as a string.
        if isinstance(params, list) and len(params) == 1 and isinstance(params[0], str):
            if params[0].startswith('[') and params[0].endswith(']'):
                try: params = eval(params[0])
                except: _LOGGER.error("Invalid params format for eval: %s", params)
            elif params[0].isnumeric(): params[0] = int(params[0])
        await self._try_command("Unable to send raw command", self._vacuum.raw_command, command, params)

    # --- Custom Services ---

    async def async_clean_zone(self, zone: list, repeats: int = 1):
        """Clean a specified zone."""
        result = []
        i = 0
        for z in zone:
            x1, y2, x2, y1 = z
            res = '_'.join(str(x) for x in [i, 0, x1, y1, x1, y2, x2, y2, x2, y1])
            for _ in range(repeats):
                result.append(res)
                i += 1
        result = [i] + result
        await self._try_command("Unable to clean zone (uploadmap)", self._vacuum.raw_command, 'set_uploadmap', [1])
        await self._try_command("Unable to clean zone (set_zone)", self._vacuum.raw_command, 'set_zone', result)
        await self._try_command("Unable to clean zone (set_mode)", self._vacuum.raw_command, 'set_mode', [3, 1])

    async def async_goto(self, x_coord: float, y_coord: float):
        """Command the vacuum to go to a specific coordinate."""
        self._last_clean_point = [x_coord, y_coord]
        await self._try_command("Unable to go to point (uploadmap)", self._vacuum.raw_command, 'set_uploadmap', [0])
        await self._try_command("Unable to go to point (set_pointclean)", self._vacuum.raw_command, 'set_pointclean', [1, x_coord, y_coord])

    async def async_clean_segment(self, segments: list[int] | int):
        """Clean one or more specified segments (rooms)."""
        if isinstance(segments, int):
            segments = [segments]
        await self._try_command("Unable to clean segment (uploadmap)", self._vacuum.raw_command, 'set_uploadmap', [1])
        await self._try_command("Unable to clean segment (set_mode_withroom)", self._vacuum.raw_command, 'set_mode_withroom', [0, 1, len(segments)] + segments)

    async def async_clean_point(self, point: list[float]):
        """Clean around a specific point."""
        self._last_clean_point = point
        await self._try_command("Unable to clean point (uploadmap)", self._vacuum.raw_command, 'set_uploadmap', [0])
        await self._try_command("Unable to clean point (set_pointclean)", self._vacuum.raw_command, 'set_pointclean', [1, point[0], point[1]])

