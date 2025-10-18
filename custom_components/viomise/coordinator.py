# -*- coding: utf-8 -*-
"""DataUpdateCoordinator for the Viomi SE integration."""

import logging
from datetime import timedelta

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from miio import Device, DeviceException

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


class ViomiSECoordinator(DataUpdateCoordinator[list]):
    """Manages fetching data from the Viomi SE vacuum and updating entities."""

    def __init__(self, hass: HomeAssistant, device: Device, scan_interval: int):
        """Initialize the data update coordinator."""
        self.device = device
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=scan_interval),
        )

    async def _async_update_data(self) -> list:
        """Fetch data from the vacuum using raw miio commands."""
        try:
            properties_to_fetch = [
                {"did": "battary_life", "siid": 3, "piid": 1},      # 0: Battery Level
                {"did": "run_state", "siid": 2, "piid": 1},        # 1: Run State
                {"did": "suction_grade", "siid": 2, "piid": 2},    # 2: Fan Speed
                {"did": "s_time", "siid": 4, "piid": 2},           # 3: Cleaning Time
                {"did": "s_area", "siid": 4, "piid": 1},           # 4: Cleaned Area
                {"did": "main_brush_life", "siid": 5, "piid": 1},  # 5: Main Brush Life
                {"did": "side_brush_life", "siid": 6, "piid": 1},  # 6: Side Brush Life
                {"did": "hypa_life", "siid": 7, "piid": 1},        # 7: Filter Life
                {"did": "mop_life", "siid": 8, "piid": 1},         # 8: Mop Life
                {"did": "water_grade", "siid": 2, "piid": 5},      # 9: Water Level
                {"did": "is_mop", "siid": 2, "piid": 7},           # 10: Mop Installed
                {"did": "mop_type", "siid": 2, "piid": 9},         # 11: Mop Pattern
            ]
            results = await self.hass.async_add_executor_job(
                self.device.send, "get_properties", properties_to_fetch
            )
            return [res.get('value') for res in results]
        except DeviceException as e:
            raise UpdateFailed(f"Error communicating with device: {e}") from e
