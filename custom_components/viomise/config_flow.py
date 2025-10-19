# custom_components/viomise/config_flow.py
"""Config flow for the Viomi SE integration."""
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
    """
    Validate that the user-provided host and token are correct.

    Connects to the device and fetches its info, which includes the MAC address.
    """
    try:
        # Use the generic miio.Device to establish a connection and get info.
        device = Device(host, token)
        info = await hass.async_add_executor_job(device.info)
        # Return the MAC address to be used as the unique ID for the config entry.
        return {"mac": info.mac_address}
    except DeviceException as e:
        # Raise a specific error that can be caught in the config flow.
        raise ConnectionError from e


class ViomiVacuumConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle the initial configuration flow for Viomi SE."""
    VERSION = 1

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: config_entries.ConfigEntry) -> config_entries.OptionsFlow:
        """Tell Home Assistant that this integration supports options flow."""
        return OptionsFlowHandler(config_entry)

    async def async_step_user(self, user_input: dict | None = None) -> FlowResult:
        """
        Handle the first step of the configuration flow, prompted by the user.

        This step collects the Host, Token, and Name.
        """
        errors: dict[str, str] = {}

        if user_input is not None:
            try:
                # Step 1: Validate the provided credentials.
                device_info = await validate_input(self.hass, user_input[CONF_HOST], user_input[CONF_TOKEN])

                # Step 2: Set the unique ID for the device to prevent duplicates.
                await self.async_set_unique_id(device_info["mac"])
                self._abort_if_unique_id_configured()

                # Step 3: If validation is successful, create the config entry.
                return self.async_create_entry(title=user_input[CONF_NAME], data=user_input)

            except ConnectionError:
                # If we can't connect, show a "cannot_connect" error.
                errors["base"] = "cannot_connect"
            except Exception:
                # For any other unexpected errors, show a generic "unknown" error.
                _LOGGER.exception("An unexpected error occurred during setup")
                errors["base"] = "unknown"

        # Define the form schema for the user to fill out.
        data_schema = vol.Schema({
            vol.Required(CONF_HOST): str,
            vol.Required(CONF_TOKEN): vol.All(str, vol.Length(min=32, max=32)),
            vol.Optional(CONF_NAME, default="Viomi SE"): str,
        })

        # Show the form to the user.
        return self.async_show_form(step_id="user", data_schema=data_schema, errors=errors)


class OptionsFlowHandler(config_entries.OptionsFlow):
    """Handle an options flow for Viomi SE to configure settings after setup."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        """Initialize the options flow."""
        self.config_entry = config_entry

    async def async_step_init(self, user_input: dict | None = None) -> FlowResult:
        """Manage the options form."""
        if user_input is not None:
            # If the user submitted the form, create the options entry and close.
            return self.async_create_entry(title="", data=user_input)

        # Define the schema for the options form.
        # The `default` values are pre-filled with the currently saved options,
        # or the default constants if no options have been saved yet.
        schema = vol.Schema({
            vol.Optional(
                CONF_COMMAND_COOLDOWN,
                default=self.config_entry.options.get(CONF_COMMAND_COOLDOWN, DEFAULT_COMMAND_COOLDOWN),
            ): vol.All(vol.Coerce(float), vol.Range(min=0.5, max=10)),
            vol.Optional(
                CONF_SCAN_INTERVAL,
                default=self.config_entry.options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL),
            ): vol.All(vol.Coerce(int), vol.Range(min=5, max=600)),
        })

        # Show the options form to the user.
        return self.async_show_form(step_id="init", data_schema=schema)

