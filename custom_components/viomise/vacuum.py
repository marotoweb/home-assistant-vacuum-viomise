# -*- coding: utf-8 -*-
"""Custom Component para Viomi Vacuum no Home Assistant, fiel ao original."""
import asyncio
import logging
from functools import partial

import voluptuous as vol
from miio import DeviceException, ViomiVacuum

from homeassistant.components.vacuum import (
    DOMAIN as VACUUM_DOMAIN,
    StateVacuumEntity,
    VacuumEntityFeature,
    # CORREÇÃO: Importar o VacuumActivity
    VacuumActivity,
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

# --- CONSTANTES, SERVIÇOS E MAPEAMENTOS ---
FAN_SPEEDS = {"Silent": 0, "Standard": 1, "Medium": 2, "Turbo": 3}
FAN_SPEEDS_REVERSE = {v: k for k, v in FAN_SPEEDS.items()}
SUPPORT_XIAOMI = (VacuumEntityFeature.PAUSE | VacuumEntityFeature.STOP | VacuumEntityFeature.RETURN_HOME | VacuumEntityFeature.FAN_SPEED | VacuumEntityFeature.LOCATE | VacuumEntityFeature.SEND_COMMAND | VacuumEntityFeature.BATTERY | VacuumEntityFeature.START | VacuumEntityFeature.STATE)

# CORREÇÃO: Mapear para a enumeração VacuumActivity
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

SERVICE_CLEAN_ZONE = "vacuum_clean_zone"; SERVICE_GOTO = "vacuum_goto"; SERVICE_CLEAN_SEGMENT = "vacuum_clean_segment"; SERVICE_CLEAN_POINT = "xiaomi_clean_point"
ATTR_ZONE_ARRAY = "zone"; ATTR_ZONE_REPEATER = "repeats"; ATTR_X_COORD = "x_coord"; ATTR_Y_COORD = "y_coord"; ATTR_SEGMENTS = "segments"; ATTR_POINT = "point"
VACUUM_SERVICE_SCHEMA = vol.Schema({vol.Optional(ATTR_ENTITY_ID): cv.entity_ids})
SERVICE_SCHEMA_CLEAN_ZONE = VACUUM_SERVICE_SCHEMA.extend({vol.Required(ATTR_ZONE_ARRAY): vol.All(list, [vol.ExactSequence([vol.Coerce(float), vol.Coerce(float), vol.Coerce(float), vol.Coerce(float)])]), vol.Required(ATTR_ZONE_REPEATER): vol.All(vol.Coerce(int), vol.Clamp(min=1, max=3))})
SERVICE_SCHEMA_GOTO = VACUUM_SERVICE_SCHEMA.extend({vol.Required(ATTR_X_COORD): vol.Coerce(float), vol.Required(ATTR_Y_COORD): vol.Coerce(float)})
SERVICE_SCHEMA_CLEAN_SEGMENT = VACUUM_SERVICE_SCHEMA.extend({vol.Required(ATTR_SEGMENTS): vol.Any(vol.Coerce(int), [vol.Coerce(int)])})
SERVICE_SCHEMA_CLEAN_POINT = VACUUM_SERVICE_SCHEMA.extend({vol.Required(ATTR_POINT): vol.All(vol.ExactSequence([vol.Coerce(float), vol.Coerce(float)]))})
SERVICE_TO_METHOD = {SERVICE_CLEAN_ZONE: {"method": "async_clean_zone", "schema": SERVICE_SCHEMA_CLEAN_ZONE}, SERVICE_GOTO: {"method": "async_goto", "schema": SERVICE_SCHEMA_GOTO}, SERVICE_CLEAN_SEGMENT: {"method": "async_clean_segment", "schema": SERVICE_SCHEMA_CLEAN_SEGMENT}, SERVICE_CLEAN_POINT: {"method": "async_clean_point", "schema": SERVICE_SCHEMA_CLEAN_POINT}}

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback):
    coordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]
    mirobo = MiroboVacuum2(coordinator, entry)
    async_add_entities([mirobo], update_before_add=True)
    
    async def async_service_handler(service):
        method_def = SERVICE_TO_METHOD.get(service.service)
        if not method_def: return
        params = {key: value for key, value in service.data.items() if key != ATTR_ENTITY_ID}
        entity_ids = service.data.get(ATTR_ENTITY_ID)
        target_vacuums = [mirobo]
        if entity_ids and mirobo.entity_id not in entity_ids: return
        for vacuum in target_vacuums:
            await getattr(vacuum, method_def["method"])(**params)

    for service_name, service_def in SERVICE_TO_METHOD.items():
        hass.services.async_register(VACUUM_DOMAIN, service_name, async_service_handler, schema=service_def.get("schema", VACUUM_SERVICE_SCHEMA))

class MiroboVacuum2(CoordinatorEntity[ViomiSECoordinator], StateVacuumEntity):
    _attr_has_entity_name = True
    _attr_name = None

    def __init__(self, coordinator: ViomiSECoordinator, config_entry: ConfigEntry):
        super().__init__(coordinator)
        self._vacuum = coordinator.vacuum
        self._attr_unique_id = config_entry.unique_id
        self._last_clean_point = None
        self._attr_device_info = {"identifiers": {(DOMAIN, self.unique_id)}, "name": config_entry.title, "manufacturer": "Viomi", "model": "V-RVCLM21A (SE)"}

    # CORREÇÃO: Remover a propriedade 'state'
    # @property
    # def state(self): ...

    # CORREÇÃO: Adicionar a propriedade 'activity'
    @property
    def activity(self) -> VacuumActivity | None:
        """Return the current vacuum activity."""
        if self.coordinator.data:
            state_code = self.coordinator.data.get("run_state")
            return STATE_CODE_TO_ACTIVITY.get(state_code)
        return None

    @property
    def battery_level(self):
        if self.coordinator.data:
            return self.coordinator.data.get("battary_life")

    @property
    def fan_speed(self):
        if self.coordinator.data:
            speed = self.coordinator.data.get("suction_grade")
            return FAN_SPEEDS_REVERSE.get(speed, speed)

    @property
    def fan_speed_list(self):
        return list(sorted(FAN_SPEEDS.keys(), key=lambda s: FAN_SPEEDS[s]))

    @property
    def extra_state_attributes(self):
        if self.coordinator.data:
            return self.coordinator.data
        return {}

    @property
    def supported_features(self):
        return SUPPORT_XIAOMI

    # O resto da classe (todos os métodos async_...) permanece exatamente igual.
    async def _try_command(self, mask_error, func, *args, **kwargs):
        try:
            await self.hass.async_add_executor_job(partial(func, *args, **kwargs))
            await self.coordinator.async_request_refresh()
            return True
        except DeviceException as exc:
            _LOGGER.error(mask_error, exc)
            return False

    async def async_start(self):
        state = self.coordinator.data;
        if not state: return
        mode = state.get('mode'); is_mop = state.get('is_mop'); actionMode = 0
        if mode == 4 and self._last_clean_point is not None: method, param = 'set_pointclean', [1, self._last_clean_point[0], self._last_clean_point[1]]
        else:
            if mode == 2: actionMode = 2
            else: actionMode = 3 if is_mop == 2 else is_mop
            if mode == 3: method, param = 'set_mode', [3, 1]
            else: method, param = 'set_mode_withroom', [actionMode, 1, 0]
        await self._try_command("Unable to start", self._vacuum.raw_command, method, param)

    async def async_pause(self):
        state = self.coordinator.data;
        if not state: return
        mode = state.get('mode'); is_mop = state.get('is_mop'); actionMode = 0
        if mode == 4 and self._last_clean_point is not None: method, param = 'set_pointclean', [3, self._last_clean_point[0], self._last_clean_point[1]]
        else:
            if mode == 2: actionMode = 2
            else: actionMode = 3 if is_mop == 2 else is_mop
            if mode == 3: method, param = 'set_mode', [3, 3]
            else: method, param = 'set_mode_withroom', [actionMode, 3, 0]
        await self._try_command("Unable to pause", self._vacuum.raw_command, method, param)

    async def async_stop(self, **kwargs):
        state = self.coordinator.data;
        if not state: return
        mode = state.get('mode')
        if mode == 3: method, param = 'set_mode', [3, 0]
        elif mode == 4:
            method, param = 'set_pointclean', [0, 0, 0]
            self._last_clean_point = None
        else: method, param = 'set_mode', [0]
        await self._try_command("Unable to stop", self._vacuum.raw_command, method, param)

    async def async_set_fan_speed(self, fan_speed, **kwargs):
        speed_value = FAN_SPEEDS.get(fan_speed.capitalize())
        if speed_value is None: _LOGGER.error("Invalid fan speed: %s", fan_speed); return
        await self._try_command("Unable to set fan speed", self._vacuum.raw_command, 'set_suction', [speed_value])

    async def async_return_to_base(self, **kwargs):
        await self._try_command("Unable to return home", self._vacuum.raw_command, 'set_charge', [1])

    async def async_locate(self, **kwargs):
        await self._try_command("Unable to locate", self._vacuum.raw_command, 'set_resetpos', [1])

    async def async_send_command(self, command, params=None, **kwargs):
        if isinstance(params, list) and len(params) == 1 and isinstance(params[0], str):
            if params[0].startswith('[') and params[0].endswith(']'):
                try: params = eval(params[0])
                except: _LOGGER.error("Invalid params format: %s", params)
            elif params[0].isnumeric(): params[0] = int(params[0])
        await self._try_command("Unable to send command", self._vacuum.raw_command, command, params)

    async def async_clean_zone(self, zone, repeats=1):
        result = []; i = 0
        for z in zone:
            x1, y2, x2, y1 = z
            res = '_'.join(str(x) for x in [i, 0, x1, y1, x1, y2, x2, y2, x2, y1])
            for _ in range(repeats): result.append(res); i += 1
        result = [i] + result
        await self._try_command("Unable to clean zone", self._vacuum.raw_command, 'set_uploadmap', [1])
        await self._try_command("Unable to clean zone", self._vacuum.raw_command, 'set_zone', result)
        await self._try_command("Unable to clean zone", self._vacuum.raw_command, 'set_mode', [3, 1])

    async def async_goto(self, x_coord, y_coord):
        self._last_clean_point = [x_coord, y_coord]
        await self._try_command("Unable to goto", self._vacuum.raw_command, 'set_uploadmap', [0])
        await self._try_command("Unable to goto", self._vacuum.raw_command, 'set_pointclean', [1, x_coord, y_coord])

    async def async_clean_segment(self, segments):
        if isinstance(segments, int): segments = [segments]
        await self._try_command("Unable to clean segments", self._vacuum.raw_command, 'set_uploadmap', [1])
        await self._try_command("Unable to clean segments", self._vacuum.raw_command, 'set_mode_withroom', [0, 1, len(segments)] + segments)

    async def async_clean_point(self, point):
        self._last_clean_point = point
        await self._try_command("Unable to clean point", self._vacuum.raw_command, 'set_uploadmap', [0])
        await self._try_command("Unable to clean point", self._vacuum.raw_command, 'set_pointclean', [1, point[0], point[1]])
