"""The Viomi SE Vacuum integration."""
from __future__ import annotations

import logging
from datetime import timedelta

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_TOKEN, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady

# Importa a TUA classe e exceção!
from .const import CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL, DOMAIN
from .viomise import ViomiSE, ViomiSEException

_LOGGER = logging.getLogger(__name__)

# Define a plataforma que esta integração vai usar (neste caso, vacuum)
PLATFORMS: list[Platform] = [Platform.VACUUM]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Viomi SE Vacuum from a config entry."""
    hass.data.setdefault(DOMAIN, {})

    # Listener para recarregar a integração quando as opções mudam
    entry.async_on_unload(entry.add_update_listener(update_listener))

    host = entry.data[CONF_HOST]
    token = entry.data[CONF_TOKEN]
    _LOGGER.info("Initializing Viomi SE integration for host %s (token: %s...)", host, token[:5])

    try:
        # Usa a TUA classe especializada, que contém o "cérebro"
        device = ViomiSE(host, token)
        await hass.async_add_executor_job(device.connect)
    except ViomiSEException as ex:
        # Usa uma exceção específica do HA para que ele tente novamente mais tarde
        raise ConfigEntryNotReady(f"Failed to initialize Viomi SE device at {host}: {ex}") from ex

    # Obtém o scan_interval das opções ou usa o valor da entrada (para migração)
    scan_interval_seconds = entry.options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
    scan_interval = timedelta(seconds=scan_interval_seconds)
    _LOGGER.debug("Using scan_interval of %s seconds", scan_interval_seconds)

    # Guarda o dispositivo e o intervalo de atualização para a plataforma usar
    hass.data[DOMAIN][entry.entry_id] = {
        "device": device,
        "scan_interval": scan_interval,
    }

    # Encaminha para a configuração da plataforma (vacuum.py)
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    # Descarrega as plataformas associadas
    _LOGGER.info("Unloading Viomi SE integration for host %s", entry.data[CONF_HOST])
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)
    return unload_ok


async def update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Handle options update."""
    _LOGGER.debug("Options updated for %s, reloading integration", entry.title)
    # Quando as opções são atualizadas, simplesmente recarregamos a integração
    await hass.config_entries.async_reload(entry.entry_id)

