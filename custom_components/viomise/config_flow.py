import logging
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_HOST, CONF_NAME, CONF_TOKEN
from homeassistant.data_entry_flow import FlowResult

DOMAIN = "viomise"
_LOGGER = logging.getLogger(__name__)

class ViomiVacuumConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Viomi Vacuum."""
    VERSION = 1

    async def async_step_user(self, user_input=None) -> FlowResult:
        """Handle the initial step."""
        errors = {}
        if user_input is not None:
            return self.async_create_entry(title=user_input[CONF_NAME], data=user_input)

        data_schema = vol.Schema({
            vol.Required(CONF_HOST): str,
            vol.Required(CONF_TOKEN): str,
            vol.Optional(CONF_NAME, default="Viomi SE"): str,
        })

        return self.async_show_form(step_id="user", data_schema=data_schema, errors=errors)
