# -*- coding: utf-8 -*-
"""Vacuum platform for Viomi SE."""

import logging
from datetime import timedelta

import homeassistant.helpers.config_validation as cv
import voluptuous as vol
# CORREÇÃO: Voltar a usar StateVacuumEntity
from homeassistant.components.vacuum import StateVacuumEntity, VacuumEntityFeature
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import ViomiSECoordinator

_LOGGER = logging.getLogger(__name__)

# Mappings
STATE_CODE_TO_STATE = {0: "Idle", 1: "Idle", 2: "Paused", 3: "Cleaning", 4: "Returning", 5: "Docked", 6: "Mopping"}
# CORREÇÃO: Adicionar o valor inesperado 2103 ao mapa de velocidades.
# É provável que seja um modo "Auto". Vamos chamá-lo de "Standard" por enquanto.
FAN_SPEEDS = {"Silent": 0, "Standard": 1, "Medium": 2, "Turbo": 3, "Auto": 2103}
FAN_SPEEDS_REVERSE = {v: k for k, v in FAN_SPEEDS.items()}
WATER_LEVELS = {"Low": 11, "Medium": 12, "High": 13}
WATER_LEVELS_REVERSE = {v: k for k, v in WATER_LEVELS.items()}
MOP_PATTERNS = {"Standard": 0, "Y-type": 1}
MOP_PATTERNS_REVERSE = {v: k for k, v in MOP_PATTERNS.items()}
CONSUMABLES = {"main_brush": 5, "side_brush": 6, "filter": 7, "mop": 8}

# CORREÇÃO: Manter a feature BATTERY, pois estamos a usar StateVacuumEntity
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
    """Set up the Viomi SE vacuum cleaner entity."""
    coordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([ViomiSE(coordinator, entry)])


class ViomiSE(CoordinatorEntity[ViomiSECoordinator], StateVacuumEntity):
    """Representation of a Viomi SE (v19) Vacuum cleaner."""
    _attr_should_poll = False
    _attr_has_entity_name = True
    _attr_name = None

    def __init__(self, coordinator: ViomiSECoordinator, config_entry: ConfigEntry):
        """Initialize the Viomi SE vacuum cleaner."""
        super().__init__(coordinator)
        self._device = coordinator.device
        self._attr_unique_id = config_entry.unique_id
        self._attr_device_info = {"identifiers": {(DOMAIN, self.unique_id)}, "name": config_entry.title, "manufacturer": "Viomi", "model": "SE (V19)"}
        self._attr_fan_speed_list = list(FAN_SPEEDS.keys())
        self._attr_supported_features = SUPPORT_VIOMISE
        self._extra_attributes = {}

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        if not self.coordinator.data:
            self._attr_available = False
            self.async_write_ha_state()
            return

        self._attr_available = True
        data = self.coordinator.data
        
        # CORREÇÃO: Usar os atributos da classe base StateVacuumEntity e verificar se os dados existem
        self._attr_battery_level = data[0] if data[0] is not None else self._attr_battery_level
        self._attr_state = STATE_CODE_TO_STATE.get(data[1], self._attr_state) if data[1] is not None else self._attr_state
        self._attr_fan_speed = FAN_SPEEDS_REVERSE.get(data[2], self._attr_fan_speed) if data[2] is not None else self._attr_fan_speed
        
        self._extra_attributes = {
            "cleaning_time": str(timedelta(seconds=data[3])) if data[3] is not None else self._extra_attributes.get("cleaning_time"),
            "cleaned_area": data[4] if data[4] is not None else self._extra_attributes.get("cleaned_area"),
            "main_brush_left": data[5] if data[5] is not None else self._extra_attributes.get("main_brush_left"),
            "side_brush_left": data[6] if data[6] is not None else self._extra_attributes.get("side_brush_left"),
            "filter_left": data[7] if data[7] is not None else self._extra_attributes.get("filter_left"),
            "mop_left": data[8] if data[8] is not None else self._extra_attributes.get("mop_left"),
            "water_level": WATER_LEVELS_REVERSE.get(data[9]) if data[9] is not None else self._extra_attributes.get("water_level"),
            "mop_installed": "Yes" if data[10] == 1 else "No" if data[10] is not None else self._extra_attributes.get("mop_installed"),
            "mop_pattern": MOP_PATTERNS_REVERSE.get(data[11]) if data[11] is not None else self._extra_attributes.get("mop_pattern"),
        }
        self.async_write_ha_state()

    @property
    def extra_state_attributes(self):
        return self._extra_attributes

    async def _execute_and_refresh(self, method, *args):
        await self.hass.async_add_executor_job(method, *args)
        await self.coordinator.async_request_refresh()

    async def async_start(self):
        await self._execute_and_refresh(self._device.send, "action", {"did": "start_clean", "siid": 2, "aiid": 1, "in": []})
    async def async_pause(self):
        await self._execute_and_refresh(self._device.send, "action", {"did": "pause_clean", "siid": 2, "aiid": 2, "in": []})
    async def async_stop(self, **kwargs):
        await self.async_pause()
    async def async_return_to_base(self, **kwargs):
        await self._execute_and_refresh(self._device.send, "action", {"did": "return_home", "siid": 3, "aiid": 1, "in": []})
    async def async_locate(self, **kwargs):
        await self._execute_and_refresh(self._device.send, "set_properties", [{"did": "find_me", "siid": 10, "piid": 1, "value": 1}])
    async def async_clean_spot(self, **kwargs):
        await self._execute_and_refresh(self._device.send, "set_properties", [{"did": "spot_clean", "siid": 2, "piid": 1, "value": 2}])
    async def async_set_fan_speed(self, fan_speed: str, **kwargs):
        if (speed_value := FAN_SPEEDS.get(fan_speed)) is not None:
            await self._execute_and_refresh(self._device.send, "set_properties", [{"did": "fan_speed", "siid": 2, "piid": 2, "value": speed_value}])
    async def async_send_command(self, command: str, params: dict | list = None, **kwargs):
        await self._execute_and_refresh(self._device.send, command, params)

    async def async_set_water_level(self, water_level: str):
        if (level_value := WATER_LEVELS.get(water_level)) is not None:
            await self._execute_and_refresh(self._device.send, "set_properties", [{"did": "water_level", "siid": 2, "piid": 5, "value": level_value}])
    async def async_set_mop_pattern(self, mop_pattern: str):
        if (pattern_value := MOP_PATTERNS.get(mop_pattern)) is not None:
            await self._execute_and_refresh(self._device.send, "set_properties", [{"did": "mop_pattern", "siid": 2, "piid": 9, "value": pattern_value}])
    async def async_reset_consumable(self, consumable: str):
        if (siid := CONSUMABLES.get(consumable)) is not None:
            await self._execute_and_refresh(self._device.send, "set_properties", [{"did": f"reset_{consumable}", "siid": siid, "piid": 1, "value": 100}])

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        @callback
        def _async_handle_service(service_call: ServiceCall, method):
            if self.entity_id not in service_call.data.get("entity_id", []): return
            params = {key: value for key, value in service_call.data.items() if key != "entity_id"}
            self.hass.async_create_task(method(**params))
        self.hass.services.async_register(DOMAIN, "set_water_level", lambda call: _async_handle_service(call, self.async_set_water_level), schema=SERVICE_SET_WATER_LEVEL_SCHEMA)
        self.hass.services.async_register(DOMAIN, "set_mop_pattern", lambda call: _async_handle_service(call, self.async_set_mop_pattern), schema=SERVICE_SET_MOP_PATTERN_SCHEMA)
        self.hass.services.async_register(DOMAIN, "reset_consumable", lambda call: _async_handle_service(call, self.async_reset_consumable), schema=SERVICE_RESET_CONSUMABLE_SCHEMA)

