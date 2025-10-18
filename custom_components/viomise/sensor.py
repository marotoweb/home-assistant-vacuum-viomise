# -*- coding: utf-8 -*-
"""Sensor platform for Viomi SE Vacuum."""
from __future__ import annotations

import logging

from homeassistant.components.sensor import SensorEntity, SensorStateClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import PERCENTAGE, EntityCategory
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import ViomiSECoordinator

_LOGGER = logging.getLogger(__name__)

SENSORS_MAPPING = {
    # CORREÇÃO: Removido o sensor de bateria daqui para evitar erros.
    # Vamos focar-nos em fazer os consumíveis funcionar primeiro.
    "main_brush_left": {"name": "Main Brush Life", "icon": "mdi:brush", "data_index": 5},
    "side_brush_left": {"name": "Side Brush Life", "icon": "mdi:brush-off", "data_index": 6},
    "filter_left": {"name": "Filter Life", "icon": "mdi:air-filter", "data_index": 7},
    "mop_left": {"name": "Mop Life", "icon": "mdi:hydro-power", "data_index": 8},
}

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    coordinator = hass.data[DOMAIN][entry.entry_id]
    entities = [ViomiSESensor(coordinator, entry, sensor_key) for sensor_key in SENSORS_MAPPING]
    async_add_entities(entities)

class ViomiSESensor(CoordinatorEntity[ViomiSECoordinator], SensorEntity):
    _attr_has_entity_name = True
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_native_unit_of_measurement = PERCENTAGE

    def __init__(self, coordinator: ViomiSECoordinator, config_entry: ConfigEntry, sensor_key: str):
        super().__init__(coordinator)
        self._sensor_key = sensor_key
        sensor_info = SENSORS_MAPPING[sensor_key]
        self._attr_unique_id = f"{config_entry.unique_id}_{sensor_key}"
        self._attr_name = sensor_info["name"]
        self._attr_icon = sensor_info["icon"]
        self._attr_device_info = {"identifiers": {(DOMAIN, config_entry.unique_id)}}
        
    @callback
    def _handle_coordinator_update(self) -> None:
        if self.coordinator.data:
            self._attr_available = True
            data_index = SENSORS_MAPPING[self._sensor_key]["data_index"]
            value = self.coordinator.data[data_index]
            try:
                # CORREÇÃO: Lidar com o caso de a 'side_brush_life' ser uma string '[1100,1100]'
                if isinstance(value, str) and value.startswith('['):
                    # Tentar extrair um valor percentual, ou usar um placeholder
                    self._attr_native_value = None # Ignorar este valor por agora
                else:
                    self._attr_native_value = int(value)
            except (ValueError, TypeError):
                self._attr_native_value = None
        else:
            self._attr_available = False
        self.async_write_ha_state()
