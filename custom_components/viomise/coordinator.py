# custom_components/viomise/coordinator.py
"""DataUpdateCoordinator for the Viomi SE integration."""
import logging
from datetime import timedelta

from miio import DeviceException, ViomiVacuum

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import (
    DataUpdateCoordinator,
    UpdateFailed,
)

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

# This list defines all the properties we want to fetch from the vacuum.
ALL_PROPS = [
    "run_state", "mode", "err_state", "battary_life", "box_type", "mop_type",
    "s_time", "s_area", "suction_grade", "water_grade", "remember_map", "has_map",
    "is_mop", "has_newmap", "main_brush_percentage", "main_brush_left",
    "side_brush_percentage", "side_brush_left", "filter_percentage", "filter_left",
    "mop_percentage", "mop_left", "repeat_state", "mop_route"
]

# This mapping is crucial for this specific vacuum model (viomi.vacuum.v19).
# It translates the human-readable property names to the required siid/piid format.
MAPPING = [
    {"did":"run_state","siid":2,"piid":1}, {"did":"mode","siid":2,"piid":18},
    {"did":"err_state","siid":2,"piid":2}, {"did":"battary_life","siid":3,"piid":1},
    {"did":"box_type","siid":2,"piid":12}, {"did":"mop_type","siid":2,"piid":13},
    {"did":"s_time","siid":2,"piid":15}, {"did":"s_area","siid":2,"piid":16},
    {"did":"suction_grade","siid":2,"piid":19}, {"did":"water_grade","siid":4,"piid":18},
    {"did":"remember_map","siid":4,"piid":3}, {"did":"has_map","siid":4,"piid":4},
    {"did":"is_mop","siid":2,"piid":11}, {"did":"has_newmap","siid":4,"piid":5},
    {"did":"main_brush_percentage","siid":4,"piid":10}, {"did":"main_brush_left","siid":4,"piid":11},
    {"did":"side_brush_percentage","siid":4,"piid":8}, {"did":"side_brush_left","siid":4,"piid":9},
    {"did":"filter_percentage","siid":4,"piid":12}, {"did":"filter_left","siid":4,"piid":13},
    {"did":"mop_left_percentage","siid":4,"piid":14}, {"did":"mop_left","siid":4,"piid":15},
    {"did":"repeat_state","siid":4,"piid":1}, {"did":"mop_route","siid":4,"piid":6}
]


class ViomiSECoordinator(DataUpdateCoordinator[dict[str, any]]):
    """Manages fetching data from the Viomi SE vacuum for all entities."""

    def __init__(self, hass: HomeAssistant, vacuum: ViomiVacuum, scan_interval: int):
        """Initialize the data update coordinator."""
        self.vacuum = vacuum
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=scan_interval),
        )

    async def _async_update_data(self) -> dict[str, any]:
        """
        Fetch data from the vacuum using the specific dual-call method.

        This device model does not return all properties in a single call.
        It requires two separate 'get_properties' calls, each with a maximum
        of 12 properties.
        """
        try:
            # First call for the first 12 properties.
            properties = await self.hass.async_add_executor_job(
                self.vacuum.raw_command, 'get_properties', MAPPING[:12]
            )
            # Second call for the remaining properties.
            properties.extend(await self.hass.async_add_executor_job(
                self.vacuum.raw_command, 'get_properties', MAPPING[12:]
            ))

            # Extract only the 'value' from each returned dictionary,
            # checking for errors (code != 0).
            state_values = [p.get('value') if p.get('code') == 0 else None for p in properties]

            # Combine the property names (ALL_PROPS) with their fetched values
            # into a single, easy-to-use dictionary.
            return dict(zip(ALL_PROPS, state_values))

        except DeviceException as e:
            # If communication fails, raise UpdateFailed to notify entities.
            raise UpdateFailed(f"Error communicating with Viomi SE device: {e}") from e

