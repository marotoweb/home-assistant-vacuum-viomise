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
        """Fetch data from the vacuum using the original 'get_prop' method."""
        try:
            # CORREÇÃO: Usar o método 'get_prop' com a lista de parâmetros,
            # exatamente como na sua integração original. Este método é mais
            # resiliente para este modelo específico.
            params = [
                "run_state", "suction_grade", "battary_life", "s_time", "s_area",
                "main_brush_life", "side_brush_life", "hypa_life", "mop_life",
                "water_grade", "is_mop", "mop_type"
            ]
            
            # O 'get_prop' retorna uma lista de valores diretamente, na ordem pedida.
            # Isto evita os erros de 'code: -4003' que estávamos a ver.
            results = await self.hass.async_add_executor_job(
                self.device.send, "get_prop", params
            )
            return results

        except DeviceException as e:
            raise UpdateFailed(f"Error communicating with device: {e}") from e
