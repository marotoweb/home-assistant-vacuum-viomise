"""Config flow for Viomi SE Vacuum."""
import logging
from typing import Any

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.const import CONF_HOST, CONF_TOKEN
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult

# Importa a TUA classe de exceção para uma validação mais precisa
from .const import CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL, DOMAIN
from .viomise import ViomiSE, ViomiSEException

_LOGGER = logging.getLogger(__name__)

# Schema para o passo inicial de configuração (ConfigFlow)
STEP_USER_DATA_SCHEMA = vol.Schema({
    vol.Required(CONF_HOST): str,
    vol.Required(CONF_TOKEN): str,
})

class ViomiSEConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Viomi SE Vacuum."""
    VERSION = 1

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}
        if user_input is not None:
            try:
                # Tenta inicializar a tua classe para validar a ligação
                viomi_device = ViomiSE(user_input[CONF_HOST], user_input[CONF_TOKEN])
                await self.hass.async_add_executor_job(viomi_device.connect)
            except ViomiSEException:
                errors["base"] = "cannot_connect"
            except Exception:
                _LOGGER.exception("Unexpected exception during config flow")
                errors["base"] = "unknown"
            else:
                # Define um unique_id para evitar duplicação
                await self.async_set_unique_id(user_input[CONF_HOST])
                self._abort_if_unique_id_configured()

                # Cria a entrada de configuração
                return self.async_create_entry(title=user_input[CONF_HOST], data=user_input)

        # Mostra o formulário ao utilizador
        return self.async_show_form(step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors)


    @staticmethod
    @callback
    def async_get_options_flow(config_entry: config_entries.ConfigEntry) -> config_entries.OptionsFlow:
        """Cria o fluxo de opções para esta entrada de configuração."""
        return ViomiSEOptionsFlowHandler(config_entry)


class ViomiSEOptionsFlowHandler(config_entries.OptionsFlow):
    """Handle an options flow for Viomi SE."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        """Initialize options flow."""
        self.config_entry = config_entry

    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        """Manage the options."""
        if user_input is not None:
            # O utilizador submeteu o formulário, guarda as opções
            return self.async_create_entry(title="", data=user_input)

        # Mostra o formulário de opções ao utilizador.
        # Os valores 'default' são preenchidos com as opções já guardadas,
        # ou com o valor padrão se ainda não existirem.
        options_schema = vol.Schema({
            vol.Optional(
                CONF_SCAN_INTERVAL,
                default=self.config_entry.options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL),
            ): vol.All(vol.Coerce(int), vol.Range(min=5)),
        })
        return self.async_show_form(step_id="init", data_schema=options_schema)

