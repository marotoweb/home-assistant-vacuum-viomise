"""Vacuum platform for the Viomi SE integration."""
import logging
from datetime import timedelta
from typing import Any

from homeassistant.components.vacuum import StateVacuumEntity, VacuumEntityFeature
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .viomise import ViomiSE  # Importa o teu cérebro

_LOGGER = logging.getLogger(__name__)

# Funcionalidades que a entidade vai expor na UI
SUPPORT_VIOMISE = (
    VacuumEntityFeature.PAUSE | VacuumEntityFeature.STOP | VacuumEntityFeature.RETURN_HOME |
    VacuumEntityFeature.FAN_SPEED | VacuumEntityFeature.BATTERY | VacuumEntityFeature.STATUS |
    VacuumEntityFeature.SEND_COMMAND | VacuumEntityFeature.LOCATE | VacuumEntityFeature.START
)


class ViomiSEVacuum(StateVacuumEntity):
    """A Home Assistant representation of a Viomi vacuum, powered by a smart core."""
    _attr_should_poll = True
    _attr_supported_features = SUPPORT_VIOMISE

    def __init__(self, device: ViomiSE, entry: ConfigEntry) -> None:
        """Initialize the entity."""
        self._device = device
        self._attr_name = entry.title
        self._attr_unique_id = entry.unique_id
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.unique_id)},
            name=entry.title,
            manufacturer="Viomi",
            model="Viomi v19 (V3 Max)",  # Modelo específico
        )

    @property
    def state(self) -> str | None:
        """Return the current state of the vacuum."""
        return self._device.get_state()

    @property
    def battery_level(self) -> int | None:
        """Return the battery level."""
        return self._device.get_battery()

    @property
    def fan_speed(self) -> str | None:
        """Return the current fan speed."""
        return self._device.get_fan_speed()

    @property
    def fan_speed_list(self) -> list[str]:
        """Return the list of supported fan speeds."""
        return self._device.fan_speeds()

    async def async_update(self) -> None:
        """Fetch the latest state by calling the update method of the smart core."""
        try:
            await self.hass.async_add_executor_job(self._device.update)
        except Exception as ex:
            _LOGGER.error("Error during vacuum state update: %s", ex)

    # --- Comandos ---
    async def async_start(self) -> None:
        await self.hass.async_add_executor_job(self._device.start)

    async def async_pause(self) -> None:
        await self.hass.async_add_executor_job(self._device.pause)

    async def async_stop(self, **kwargs: Any) -> None:
        await self.hass.async_add_executor_job(self._device.stop)

    async def async_return_to_base(self, **kwargs: Any) -> None:
        await self.hass.async_add_executor_job(self._device.home)

    async def async_set_fan_speed(self, fan_speed: str, **kwargs: Any) -> None:
        await self.hass.async_add_executor_job(self._device.set_fan_speed, fan_speed)

    async def async_send_command(self, command: str, params: dict | list | None = None, **kwargs: Any) -> None:
        await self.hass.async_add_executor_job(self._device.send_command, command, params)

    async def async_locate(self, **kwargs):
        """Locate the vacuum cleaner."""
        await self._try_command("Unable to locate the botvac: %s", self._vacuum.raw_command, 'set_resetpos', [1])

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    """Set up the vacuum platform."""
    data = hass.data[DOMAIN][entry.entry_id]
    device: ViomiSE = data["device"]
    scan_interval: timedelta = data["scan_interval"]

    vacuum = ViomiSEVacuum(device, entry)
    vacuum.SCAN_INTERVAL = scan_interval
    async_add_entities([vacuum])

