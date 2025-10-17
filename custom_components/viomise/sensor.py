# custom_components/viomise/sensor.py

import logging
from typing import Callable

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import PERCENTAGE, TIME_HOURS
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo, EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .viomise import ViomiSE

_LOGGER = logging.getLogger(__name__)

# Define all sensors
# Each tuple is: (entity_name, key_in_vacuum_state, unit, device_class, entity_category, icon)
SENSORS = [
    ("Battery", "battary_life", PERCENTAGE, SensorDeviceClass.BATTERY, EntityCategory.DIAGNOSTIC, "mdi:battery"),
    ("Main Brush Left", "main_brush_left_percentage", PERCENTAGE, None, EntityCategory.DIAGNOSTIC, "mdi:brush"),
    ("Side Brush Left", "side_brush_left_percentage", PERCENTAGE, None, EntityCategory.DIAGNOSTIC, "mdi:brush-outline"),
    ("Filter Left", "filter_left_percentage", PERCENTAGE, None, EntityCategory.DIAGNOSTIC, "mdi:air-filter"),
    ("Mop Left", "mop_left_percentage", PERCENTAGE, None, EntityCategory.DIAGNOSTIC, "mdi:water-opacity"),
    ("Main Brush Time Left", "main_brush_left", TIME_HOURS, None, EntityCategory.DIAGNOSTIC, "mdi:clock-outline"),
    ("Side Brush Time Left", "side_brush_left", TIME_HOURS, None, EntityCategory.DIAGNOSTIC, "mdi:clock-outline"),
    ("Filter Time Left", "filter_left", TIME_HOURS, None, EntityCategory.DIAGNOSTIC, "mdi:clock-outline"),
    ("Mop Time Left", "mop_left", TIME_HOURS, None, EntityCategory.DIAGNOSTIC, "mdi:clock-outline"),
]

async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the sensor platform."""
    coordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]
    device = hass.data[DOMAIN][entry.entry_id]["device"]

    entities = [
        ViomiSESensor(coordinator, device, entry, name, key, unit, dclass, eclass, icon)
        for name, key, unit, dclass, eclass, icon in SENSORS
    ]
    async_add_entities(entities)


class ViomiSESensor(CoordinatorEntity, SensorEntity):
    """Representation of a Viomi SE Sensor."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: DataUpdateCoordinator,
        device: ViomiSE,
        entry: ConfigEntry,
        name: str,
        state_key: str,
        unit: str,
        device_class: SensorDeviceClass | None,
        entity_category: EntityCategory,
        icon: str,
    ):
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._device = device
        self._state_key = state_key

        self._attr_name = name
        self._attr_unique_id = f"{entry.unique_id}_{state_key}"
        self._attr_native_unit_of_measurement = unit
        self._attr_device_class = device_class
        self._attr_entity_category = entity_category
        self._attr_icon = icon
        self._attr_state_class = SensorStateClass.MEASUREMENT

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, str(entry.unique_id))},
        )

    @property
    def native_value(self) -> StateType | int | None:
        """Return the state of the sensor."""
        if self.coordinator.data is None or self._device.vacuum_state is None:
            return None
        return self._device.vacuum_state.get(self._state_key)

