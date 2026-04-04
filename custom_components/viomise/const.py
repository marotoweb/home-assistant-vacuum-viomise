# custom_components/viomise/const.py
"""Constants for the Viomi SE integration."""

# The domain of the integration. This must be unique and match the folder name.
DOMAIN = "viomise"

# Configuration keys used in config_flow.py and __init__.py.
CONF_HOST = "host"
CONF_TOKEN = "token"
CONF_NAME = "name"

# Options keys used in the options flow.
CONF_COMMAND_COOLDOWN = "command_cooldown"
CONF_SCAN_INTERVAL = "scan_interval"

# Default values for the options, used as a fallback.
DEFAULT_COMMAND_COOLDOWN = 2.5  # seconds
DEFAULT_SCAN_INTERVAL = 30      # seconds

