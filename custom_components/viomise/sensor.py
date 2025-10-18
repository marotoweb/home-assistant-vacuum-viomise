# -*- coding: utf-8 -*-
"""Sensor platform for Viomi SE Vacuum."""
from __future__ import annotations

import logging

from homeassistant.components.sensor import SensorEntity, SensorStateClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import PERCENTAGE, EntityCategory
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity import EntityDescription
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import ViomiSECoordinator

_LOGGER = logging.getLogger(__name__)

# Describes the sensors that will be created.
# CORREÇÃO: Removido 'state_class' e 'entity_category' da EntityDescription
# para garantir compatibilidade com versões mais antigas do HA.
SENSOR_DESCRIPTIONS: tuple[EntityDescription, ...] = (
    EntityDescription(key="main_brush_left", name="Main Brush Life", icon="mdi:brush", unit_of_measurement=PERCENTAGE),
    EntityDescription(key="side_brush_left", name="Side Brush Life", icon="mdi:brush-off", unit_of_measurement=PERCENTAGE),
    EntityDescription(key="filter_left", name="Filter Life", icon="mdi:air-filter", unit_of_measurement=PERCENTAGE),
    EntityDescription(key="mop_left", name="Mop Life", icon="mdi:hydro-power", unit_of_measurement=PERCENTAGE),
)
# Map key to data index from coordinator
SENSOR_DATA_INDEX = {"main_brush_left": 5, "side_brush_left": 6, "filter_left": 7, "mop_left": 8}


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    """Set up the Viomi SE sensor platform."""
    coordinator = hass.data[DOMAIN][entry.entry_id]
    entities = [ViomiSEConsumableSensor(coordinator, entry, description) for description in SENSOR_DESCRIPTIONS]
    async_add_entities(entities)


class ViomiSEConsumableSensor(CoordinatorEntity[ViomiSECoordinator], SensorEntity):
    """A sensor for a Viomi SE consumable."""
    _attr_has_entity_name = True
    
    # CORREÇÃO: Definir 'state_class' e 'entity_category' como atributos da classe
    # em vez de na EntityDescription.
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, coordinator: ViomiSECoordinator, config_entry: ConfigEntry, description: EntityDescription):
        """Initialize the sensor."""
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{config_entry.unique_id}_{description.key}"
        
        self._attr_device_info = {"identifiers": {(DOMAIN, config_entry.unique_id)}}
        
    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        if self.coordinator.data:
            data_index = SENSOR_DATA_INDEX[self.entity_description.key]
            self._attr_native_value = self.coordinator.data[data_index]
            self.async_write_ha_state()

