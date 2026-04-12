# custom_components/viomise/sensor.py
"""Sensor platform for Viomi SE consumables and battery."""
from __future__ import annotations
import logging 
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
from homeassistant.exceptions import ConfigEntryNotReady

from .const import DOMAIN
from .coordinator import ViomiSECoordinator

_LOGGER = logging.getLogger(__name__)

# By using a dataclass, we can extend the standard SensorEntityDescription
# with our own custom fields, in this case, 'value_key'.
@dataclass(frozen=True, kw_only=True)
class ViomiSESensorEntityDescription(SensorEntityDescription):
    """Describes a Viomi SE sensor entity."""
    # This key maps the sensor to the specific value in the coordinator's data dictionary.
    value_key: str

# This tuple defines all the sensors that will be created by the integration.
# This modern approach makes it very easy to add or remove sensors in the future
# by simply adding or removing an entry from this list.
SENSOR_DESCRIPTIONS: tuple[ViomiSESensorEntityDescription, ...] = (
    ViomiSESensorEntityDescription(
        key="battery",
        name="Battery",  # The name will be translated by Home Assistant.
        device_class=SensorDeviceClass.BATTERY,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=PERCENTAGE,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_key="battary_life",
    ),
    ViomiSESensorEntityDescription(
        key="main_brush_left",
        name="Main Brush Life",  # The name will be translated.
        icon="mdi:brush",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=PERCENTAGE,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_key="main_brush_percentage",
    ),
    ViomiSESensorEntityDescription(
        key="side_brush_left",
        name="Side Brush Life",  # The name will be translated.
        icon="mdi:brush-outline",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=PERCENTAGE,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_key="side_brush_percentage",
    ),
    ViomiSESensorEntityDescription(
        key="filter_left",
        name="Filter Life",  # The name will be translated.
        icon="mdi:air-filter",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=PERCENTAGE,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_key="filter_percentage",
    ),
    ViomiSESensorEntityDescription(
        key="mop_left",
        name="Mop Life",  # The name will be translated.
        icon="mdi:water-pump", # Changed from hydro-power to be more representative.
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=PERCENTAGE,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_key="mop_percentage",
    ),
)

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    """Set up the Viomi SE sensor platform from a config entry."""
    
    _LOGGER.debug("Setting up sensor platform for entry %s", entry.entry_id)
    
    # The coordinator is guaranteed to be ready by __init__.py before calling
    # async_forward_entry_setups, so we can safely retrieve it here.
    try:
        coordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]
    except KeyError as e:
        _LOGGER.error("Failed to get coordinator from hass.data: %s", e)
        _LOGGER.error("Available data: %s", hass.data.get(DOMAIN, {}).get(entry.entry_id, {}))
        raise ConfigEntryNotReady(f"Coordinator not found for {entry.entry_id}") from e
    
    _LOGGER.debug("Coordinator found. Data keys: %s", list(coordinator.data.keys()) if coordinator.data else "None")
    
    # Create a list of sensor entities based on the SENSOR_DESCRIPTIONS tuple.
    entities = [
        ViomiSESensor(coordinator, entry, description)
        for description in SENSOR_DESCRIPTIONS
    ]
    _LOGGER.debug("Adding %d sensor entities", len(entities))
    async_add_entities(entities)

class ViomiSESensor(CoordinatorEntity[ViomiSECoordinator], SensorEntity):
    """Representation of a Viomi SE Sensor that fetches data from the coordinator."""
    _attr_has_entity_name = True
    entity_description: ViomiSESensorEntityDescription

    def __init__(
        self,
        coordinator: ViomiSECoordinator,
        config_entry: ConfigEntry,
        description: ViomiSESensorEntityDescription,
    ):
        """Initialize the sensor and link it to the coordinator."""
        super().__init__(coordinator)
        self.entity_description = description
        
        # Use config_entry.entry_id for unique_id if unique_id is not set
        unique_id = config_entry.unique_id or config_entry.entry_id
        self._attr_unique_id = f"{unique_id}_{description.key}"
        
        # Use dynamic device information from miIO.info stored in the coordinator.
        info = coordinator.device_info_data
        
        # Link this sensor to the same device as the vacuum entity.
        self._attr_device_info = {
                "identifiers": {(DOMAIN, config_entry.unique_id)},
                "name": config_entry.title,
                "manufacturer": "Viomi",
                "model": info.get("model", "Viomi SE (V19)"),
                "sw_version": info.get("fw_ver"),
                "hw_version": info.get("hw_ver"),
                "connections": {("mac", info.get("mac"))},
            }

    @property
    def native_value(self) -> int | None:
        """Return the state of the sensor from the coordinator's data."""
        if self.coordinator.data:
            # Use the 'value_key' from the entity description to get the correct
            # value from the coordinator's data dictionary.
            return self.coordinator.data.get(self.entity_description.value_key)
        return None
