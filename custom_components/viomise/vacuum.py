# -*- coding: utf-8 -*-
"""Vacuum platform for Viomi SE."""

import logging
from datetime import timedelta

import homeassistant.helpers.config_validation as cv
import voluptuous as vol
from homeassistant.components.vacuum import StateVacuumEntity, VacuumEntityFeature
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import ViomiSECoordinator

_LOGGER = logging.getLogger(__name__)

# Mappings based on original, working implementation
STATE_CODE_TO_STATE = {0: "Idle", 1: "Idle", 2: "Paused", 3: "Cleaning", 4: "Returning", 5: "Docked", 6: "Mopping"}
FAN_SPEEDS = {"Silent": 0, "Standard": 1, "Medium": 2, "Turbo": 3}
FAN_SPEEDS_REVERSE = {v: k for k, v in FAN_SPEEDS.items()}
WATER_LEVELS = {"Low": 11, "Medium": 12, "High": 13}
WATER_LEVELS_REVERSE = {v: k for k, v in WATER_LEVELS.items()}
MOP_PATTERNS = {"Standard": 0, "Y-type": 1}
MOP_PATTERNS_REVERSE = {v: k for k, v in MOP_PATTERNS.items()}
CONSUMABLES = {"main_brush": 5, "side_brush": 6, "filter": 7, "mop": 8}

SUPPORT_VIOMISE = (
    VacuumEntityFeature.PAUSE | VacuumEntityFeature.STOP | VacuumEntityFeature.RETURN_HOME |
    VacuumEntityFeature.FAN_SPEED | VacuumEntityFeature.BATTERY | VacuumEntityFeature.STATUS |
    VacuumEntityFeature.SEND_COMMAND | VacuumEntityFeature.LOCATE | VacuumEntityFeature.CLEAN_SPOT |
    VacuumEntityFeature.START
)

# Service Schemas
SERVICE_SET_WATER_LEVEL_SCHEMA = vol.Schema({vol.Required('entity_id'): cv.entity_id, vol.Required('water_level'): vol.In(list(WATER_LEVELS.keys()))})
SERVICE_SET_MOP_PATTERN_SCHEMA = vol.Schema({vol.Required('entity_id'): cv.entity_id, vol.Required('mop_pattern'): vol.In(list(MOP_PATTERNS.keys()))})
SERVICE_RESET_CONSUMABLE_SCHEMA = vol.Schema({vol.Required('entity_id'): cv.entity_id, vol.Required('consumable'): vol.In(list(CONSUMABLES.keys()))})


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    coordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([ViomiSE(coordinator, entry)])


class ViomiSE(CoordinatorEntity[ViomiSECoordinator], StateVacuumEntity):
    _attr_should_poll = False
    _attr_has_entity_name = True
    _attr_name = None

    def __init__(self, coordinator: ViomiSECoordinator, config_entry: ConfigEntry):
        super().__init__(coordinator)
        self._device = coordinator.device
        self._attr_unique_id = config_entry.unique_id
        self._attr_device_info = {"identifiers": {(DOMAIN, self.unique_id)}, "name": config_entry.title, "manufacturer": "Viomi", "model": "SE (V19)"}
        self._attr_fan_speed_list = list(FAN_SPEEDS.keys())
        self._attr_supported_features = SUPPORT_VIOMISE
        self._extra_attributes = {}

    @callback
    def _handle_coordinator_update(self) -> None:
        if not self.coordinator.data or len(self.coordinator.data) < 12:
            self._attr_available = False
            self.async_write_ha_state()
            return

        self._attr_available = True
        data = self.coordinator.data
        
        # Data order from get_prop:
        # 0:run_state, 1:suction_grade, 2:battary_life, 3:s_time, 4:s_area,
        # 5:main_brush_life, 6:side_brush_life, 7:hypa_life, 8:mop_life,
        # 9:water_grade, 10:is_mop, 11:mop_type

        self._attr_state = STATE_CODE_TO_STATE.get(data[0])
        self._attr_fan_speed = FAN_SPEEDS_REVERSE.get(data[1])
        self._attr_battery_level = data[2]
        
        self._extra_attributes = {
            "cleaning_time": str(timedelta(seconds=data[3] or 0)),
            "cleaned_area": data[4],
            "main_brush_left": data[5],
            "side_brush_left": data[6],
            "filter_left": data[7],
            "mop_left": data[8],
            "water_level": WATER_LEVELS_REVERSE.get(data[9]),
            "mop_installed": "Yes" if data[10] == 1 else "No",
            "mop_pattern": MOP_PATTERNS_REVERSE.get(data[11]),
        }
        self.async_write_ha_state()

    @property
    def extra_state_attributes(self):
        return self._extra_attributes

    async def _execute_and_refresh(self, method, *args):
        """Execute a command and then trigger a coordinator refresh."""
        await self.hass.async_add_executor_job(method, *args)
        # Add a small delay to give the vacuum time to process the command before refreshing
        await asyncio.sleep(1)
        await self.coordinator.async_request_refresh()

    # --- Control Methods based on original, working implementation ---
    async def async_start(self):
        await self._execute_and_refresh(self._device.send, "set_mode_withroom", [0, 1, 0])

    async def async_pause(self):
        await self._execute_and_refresh(self._device.send, "set_mode_withroom", [0, 2, 0])

    async def async_stop(self, **kwargs):
        await self._execute_and_refresh(self._device.send, "set_mode_withroom", [0, 0, 0])

    async def async_return_to_base(self, **kwargs):
        await self._execute_and_refresh(self._device.send, "set_charge", [1])

    async def async_locate(self, **kwargs):
        # CORREÇÃO: Restaurado o comando 'set_resetpos' original para localizar.
        await self._execute_and_refresh(self._device.send, "set_resetpos", [1])

    async def async_clean_spot(self, **kwargs):
        await self._execute_and_refresh(self._device.send, "set_mode", [2])

    async def async_set_fan_speed(self, fan_speed: str, **kwargs):
        if (speed_value := FAN_SPEEDS.get(fan_speed)) is not None:
            await self._execute_and_refresh(self._device.send, "set_suction", [speed_value])

    async def async_send_command(self, command: str, params: dict | list = None, **kwargs):
        await self._execute_and_refresh(self._device.send, command, params)

    # --- Custom Service Methods ---
    async def async_set_water_level(self, water_level: str):
        if (level_value := WATER_LEVELS.get(water_level)) is not None:
            # Este comando usa set_properties, que parece ser para configurações mais específicas
            await self._execute_and_refresh(self._device.send, "set_properties", [{"did": "water_level", "siid": 2, "piid": 5, "value": level_value}])

    async def async_set_mop_pattern(self, mop_pattern: str):
        if (pattern_value := MOP_PATTERNS.get(mop_pattern)) is not None:
            await self._execute_and_refresh(self._device.send, "set_properties", [{"did": "mop_pattern", "siid": 2, "piid": 9, "value": pattern_value}])

    async def async_reset_consumable(self, consumable: str):
        if (siid := CONSUMABLES.get(consumable)) is not None:
            await self._execute_and_refresh(self._device.send, "set_properties", [{"did": f"reset_{consumable}", "siid": siid, "piid": 1, "value": 100}])

    async def async_added_to_hass(self) -> None:
        """Register services when entity is added."""
        await super().async_added_to_hass()
        # O resto do código de registo de serviços permanece igual
        @callback
        def _async_handle_service(service_call: ServiceCall, method):
            if self.entity_id not in service_call.data.get("entity_id", []): return
            params = {key: value for key, value in service_call.data.items() if key != "entity_id"}
            self.hass.async_create_task(method(**params))
        self.hass.services.async_register(DOMAIN, "set_water_level", lambda call: _async_handle_service(call, self.async_set_water_level), schema=SERVICE_SET_WATER_LEVEL_SCHEMA)
        self.hass.services.async_register(DOMAIN, "set_mop_pattern", lambda call: _async_handle_service(call, self.async_set_mop_pattern), schema=SERVICE_SET_MOP_PATTERN_SCHEMA)
        self.hass.services.async_register(DOMAIN, "reset_consumable", lambda call: _async_handle_service(call, self.async_reset_consumable), schema=SERVICE_RESET_CONSUMABLE_SCHEMA)

