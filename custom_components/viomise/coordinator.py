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
                {"did": "battary_life", "siid": 3, "piid": 1},      # 0
                {"did": "run_state", "siid": 2, "piid": 1},        # 1
                {"did": "suction_grade", "siid": 2, "piid": 2},    # 2
                {"did": "s_time", "siid": 4, "piid": 2},           # 3
                {"did": "s_area", "siid": 4, "piid": 1},           # 4
                {"did": "main_brush_life", "siid": 5, "piid": 1},  # 5
                {"did": "side_brush_life", "siid": 6, "piid": 1},  # 6
                {"did": "hypa_life", "siid": 7, "piid": 1},        # 7
                {"did": "mop_life", "siid": 8, "piid": 1},         # 8
                {"did": "water_grade", "siid": 2, "piid": 5},      # 9
                {"did": "is_mop", "siid": 2, "piid": 7},           # 10
                {"did": "mop_type", "siid": 2, "piid": 9},         # 11
            ]
            results = await self.hass.async_add_executor_job(
                self.device.send, "get_properties", properties_to_fetch
            )
            
            # CORREÇÃO: Verificar o 'code' de cada resultado. Se for diferente de 0, o valor é inválido.
            return [res.get('value') if res.get('code') == 0 else None for res in results]

        except DeviceException as e:
            raise UpdateFailed(f"Error communicating with device: {e}") from e
git