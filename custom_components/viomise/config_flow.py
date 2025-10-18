# custom_components/viomise/config_flow.py
# -*- coding: utf-8 -*-
"""Config flow for Viomi SE integration."""
import logging

import voluptuous as vol
from miio import Device, DeviceException

from homeassistant import config_entries
from homeassistant.core import HomeAssistant, callback
from homeassistant.data_entry_flow import FlowResult

from .const import (
    CONF_COMMAND_COOLDOWN,
    CONF_HOST,
    CONF_NAME,
    CONF_SCAN_INTERVAL,
    CONF_TOKEN,
    DEFAULT_COMMAND_COOLDOWN,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)

async def validate_input(hass: HomeAssistant, host: str, token: str) -> dict:
    """Validate that we can connect to the device."""
    try:
        # Use the generic Device class here just to test the connection
        device = Device(host, token)
        info = await hass.async_add_executor_job(device.info)
        # Return the MAC address to use as the unique ID for the device
        return {"mac": info.mac_address}
    except DeviceException as e:
        # If we can't connect, raise a specific error to be caught in the flow
        raise ConnectionError from e

class ViomiVacuumConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Viomi SE."""
    VERSION = 1

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: config_entries.ConfigEntry) -> config_entries.OptionsFlow:
        """Get the options flow for this handler."""
        return OptionsFlowHandler(config_entry)

    async def async_step_user(self, user_input=None) -> FlowResult:
        """Handle the initial step of the user configuration."""
        errors: dict[str, str] = {}

        if user_input is not None:
            try:
                # Step 1: Validate the user's input
                device_info = await validate_input(self.hass, user_input[CONF_HOST], user_input[CONF_TOKEN])

                # Step 2: Set a unique ID for the entry to prevent duplicates
                await self.async_set_unique_id(device_info["mac"])
                self._abort_if_unique_id_configured()

                # Step 3: If everything is valid, create the config entry
                return self.async_create_entry(title=user_input[CONF_NAME], data=user_input)

            except ConnectionError:
                errors["base"] = "cannot_connect"
            except Exception:
                errors["base"] = "unknown"

        data_schema = vol.Schema({
            vol.Required(CONF_HOST): str,
            vol.Required(CONF_TOKEN): vol.All(str, vol.Length(min=32, max=32)),
            vol.Optional(CONF_NAME, default="Viomi SE"): str,
        })
        return self.async_show_form(step_id="user", data_schema=data_schema, errors=errors)

class OptionsFlowHandler(config_entries.OptionsFlow):
    """Handle an options flow for Viomi SE."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        """Initialize options flow."""
        self.config_entry = config_entry

    async def async_step_init(self, user_input: dict | None = None) -> FlowResult:
        """Manage the options."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        # Formulário com ambos os campos
        schema = vol.Schema(
            {
                vol.Optional(
                    CONF_COMMAND_COOLDOWN,
                    default=self.config_entry.options.get(
                        CONF_COMMAND_COOLDOWN, DEFAULT_COMMAND_COOLDOWN
                    ),
                ): vol.All(vol.Coerce(float), vol.Range(min=0.5, max=10)),
                vol.Optional(
                    CONF_SCAN_INTERVAL,
                    default=self.config_entry.options.get(
                        CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL
                    ),
                ): vol.All(vol.Coerce(int), vol.Range(min=5, max=600)),
            }
        )
        return self.async_show_form(step_id="init", data_schema=schema)

