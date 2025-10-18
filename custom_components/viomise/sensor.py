# custom_components/viomise/sensor.py
# -*- coding: utf-8 -*-
"""Sensor platform for Viomi SE."""
from __future__ import annotations

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import PERCENTAGE, EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import ViomiSECoordinator

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    """Set up the Viomi SE sensor platform."""
    coordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]
    async_add_entities([ViomiSEBatterySensor(coordinator, entry)])


class ViomiSEBatterySensor(CoordinatorEntity[ViomiSECoordinator], SensorEntity):
    """Representation of a Viomi SE Battery Sensor."""
    _attr_has_entity_name = True
    
    # Define as características do sensor
    _attr_device_class = SensorDeviceClass.BATTERY
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = PERCENTAGE
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, coordinator: ViomiSECoordinator, config_entry: ConfigEntry):
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{config_entry.unique_id}_battery"
        self._attr_name = "Battery" # O nome será "Viomi SE Battery"
        
        # Liga este sensor ao mesmo dispositivo que o aspirador
        self._attr_device_info = {
            "identifiers": {(DOMAIN, config_entry.unique_id)}
        }

    @property
    def native_value(self) -> int | None:
        """Return the state of the sensor."""
        if self.coordinator.data:
            return self.coordinator.data.get("battary_life")
        return None
