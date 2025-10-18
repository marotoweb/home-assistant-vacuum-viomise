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
        """Fetch data from the vacuum using the 'get_properties' method with did/siid/piid."""
        try:
            # CORREÇÃO FINAL: Voltar a usar 'get_properties' com a sintaxe completa,
            # que sabemos que retorna dados, mesmo que com alguns erros.
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
            
            # A verificação de 'code' é crucial aqui para lidar com os erros -4003.
            # Se houver um erro, o valor será None, e o vacuum.py saberá como lidar com isso.
            processed_results = [res.get('value') if res.get('code') == 0 else None for res in results]
            
            # Re-mapear para a ordem que o vacuum.py espera, caso 'get_properties' não garanta a ordem
            # (embora normalmente garanta). Esta é uma segurança extra.
            param_order = [
                "battary_life", "run_state", "suction_grade", "s_time", "s_area",
                "main_brush_life", "side_brush_life", "hypa_life", "mop_life",
                "water_grade", "is_mop", "mop_type"
            ]
            
            # Criar um dicionário de resultados para mapeamento seguro
            result_map = {res['did']: res for res in results}

            # Reconstruir a lista na ordem correta, respeitando os erros
            final_results = []
            for did in param_order:
                res = result_map.get(did)
                if res and res.get('code') == 0:
                    final_results.append(res.get('value'))
                else:
                    final_results.append(None)
            
            # A ordem no vacuum.py é diferente, vamos ajustar aqui para não mexer mais lá
            # Ordem no vacuum.py: run_state, suction_grade, battary_life, ...
            final_ordered_list = [
                final_results[1], # run_state
                final_results[2], # suction_grade
                final_results[0], # battary_life
                final_results[3], # s_time
                final_results[4], # s_area
                final_results[5], # main_brush_life
                final_results[6], # side_brush_life
                final_results[7], # hypa_life
                final_results[8], # mop_life
                final_results[9], # water_grade
                final_results[10], # is_mop
                final_results[11], # mop_type
            ]
            
            return final_ordered_list

        except DeviceException as e:
            raise UpdateFailed(f"Error communicating with device: {e}") from e
