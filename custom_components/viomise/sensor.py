# custom_components/viomise/sensor.py
# -*- coding: utf-8 -*-
"""Sensor platform for Viomi SE consumables and battery."""
from __future__ import annotations
from dataclasses import dataclass

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import PERCENTAGE, EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import ViomiSECoordinator

# Usamos dataclass para adicionar o nosso próprio campo 'value_key' à descrição da entidade.
@dataclass(frozen=True, kw_only=True)
class ViomiSESensorEntityDescription(SensorEntityDescription):
    """Describes a Viomi SE sensor entity."""
    # A chave no dicionário de dados do coordinator que este sensor irá ler.
    value_key: str

# Lista de descrições para todos os nossos sensores.
# Isto torna a adição de novos sensores no futuro muito fácil.
SENSOR_DESCRIPTIONS: tuple[ViomiSESensorEntityDescription, ...] = (
    ViomiSESensorEntityDescription(
        key="battery",
        name="Battery", # O nome será traduzido
        device_class=SensorDeviceClass.BATTERY,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=PERCENTAGE,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_key="battary_life",
    ),
    ViomiSESensorEntityDescription(
        key="main_brush_left",
        name="Main Brush Life", # O nome será traduzido
        icon="mdi:brush",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=PERCENTAGE,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_key="main_brush_percentage",
    ),
    ViomiSESensorEntityDescription(
        key="side_brush_left",
        name="Side Brush Life", # O nome será traduzido
        icon="mdi:brush-outline",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=PERCENTAGE,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_key="side_brush_percentage",
    ),
    ViomiSESensorEntityDescription(
        key="filter_left",
        name="Filter Life", # O nome será traduzido
        icon="mdi:air-filter",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=PERCENTAGE,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_key="filter_percentage",
    ),
    ViomiSESensorEntityDescription(
        key="mop_left",
        name="Mop Life", # O nome será traduzido
        icon="mdi:hydro-power",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=PERCENTAGE,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_key="mop_percentage",
    ),
)

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    """Set up the Viomi SE sensor platform."""
    coordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]
    
    # Cria uma lista de entidades de sensor com base nas descrições
    entities = [
        ViomiSESensor(coordinator, entry, description)
        for description in SENSOR_DESCRIPTIONS
    ]
    async_add_entities(entities)

class ViomiSESensor(CoordinatorEntity[ViomiSECoordinator], SensorEntity):
    """Representation of a Viomi SE Sensor."""
    _attr_has_entity_name = True
    entity_description: ViomiSESensorEntityDescription

    def __init__(
        self,
        coordinator: ViomiSECoordinator,
        config_entry: ConfigEntry,
        description: ViomiSESensorEntityDescription,
    ):
        """Initialize the sensor."""
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{config_entry.unique_id}_{description.key}"
        
        # Liga este sensor ao mesmo dispositivo que o aspirador
        self._attr_device_info = {
            "identifiers": {(DOMAIN, config_entry.unique_id)}
        }

    @property
    def native_value(self) -> int | None:
        """Return the state of the sensor."""
        if self.coordinator.data:
            # Usa a 'value_key' da descrição para obter o valor correto do coordinator
            return self.coordinator.data.get(self.entity_description.value_key)
        return None
