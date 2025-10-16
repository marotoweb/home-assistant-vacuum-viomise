"""
The smart core for the Viomi v19 integration.

This file contains the ViomiSE class, which handles all direct communication
with the vacuum, state parsing, and business logic like auto-correcting the mop mode.
"""
import logging
from typing import Any, Dict, List

from miio import Device, DeviceException

_LOGGER = logging.getLogger(__name__)

# Custom Exception for better error handling
class ViomiSEException(Exception):
    """Base exception for Viomi SE device errors."""
    pass

# Mapping of all properties to be fetched from the device
# Based on the official miot-spec-v2 for viomi.vacuum.v19
# Each dict contains: did (local name), siid (Service ID), piid (Property ID)
ALL_PROPS = [
    {"did": "run_state", "siid": 2, "piid": 1},
    {"did": "err_state", "siid": 2, "piid": 2},
    {"did": "is_mop", "siid": 2, "piid": 11},      # The mode we auto-correct
    {"did": "box_type", "siid": 2, "piid": 12},     # Sensor: Type of box installed
    {"did": "mop_type", "siid": 2, "piid": 13},     # Sensor: Mop attachment present
    {"did": "s_time", "siid": 2, "piid": 15},
    {"did": "s_area", "siid": 2, "piid": 16},
    {"did": "suction_grade", "siid": 2, "piid": 19},
    {"did": "battery_life", "siid": 3, "piid": 1},
    {"did": "water_grade", "siid": 4, "piid": 18},
    {"did": "remember_map", "siid": 4, "piid": 3},
    {"did": "has_map", "siid": 4, "piid": 4},
    {"did": "has_newmap", "siid": 4, "piid": 5},
    {"did": "mop_route", "siid": 4, "piid": 6},
    {"did": "main_brush_left", "siid": 4, "piid": 11},
    {"did": "side_brush_left", "siid": 4, "piid": 9},
    {"did": "filter_left", "siid": 4, "piid": 13},
    {"did": "mop_left", "siid": 4, "piid": 15},
    {"did": "repeat_state", "siid": 4, "piid": 1},
]

# Mappings to translate raw state codes into human-readable strings
STATE_MAPPING = {
    0: "Sleeping",
    1: "Idle",
    2: "Paused",
    3: "Returning to base",
    4: "Charging",
    5: "Cleaning",
    6: "Cleaning and Mopping",
    7: "Mopping",
}

FAN_SPEED_MAPPING = {
    0: "Silent",
    1: "Standard",
    2: "Medium",
    3: "Turbo",
}
FAN_SPEED_MAPPING_REVERSE = {v: k for k, v in FAN_SPEED_MAPPING.items()}

class ViomiSE:
    """
    Main class for handling communication with the Viomi v19 vacuum.
    This class contains an instance of miio.Device and adds smart logic on top.
    """
    def __init__(self, ip: str, token: str):
        """Initialize the device communication handler. No I/O is done here."""
        _LOGGER.debug("Initializing ViomiSE handler for IP: %s", ip)
        self.ip = ip
        self.token = token
        self._device = Device(ip, token)
        self.vacuum_state: Dict[str, Any] = {}

    def connect(self) -> bool:
        """
        Establish connection to the device and get basic info.
        This is a blocking call and should be run in an executor.
        """
        try:
            self._device.info()
            _LOGGER.debug("Successfully connected to device %s", self.ip)
            return True
        except DeviceException as e:
            _LOGGER.error("Failed to connect to device %s: %s", self.ip, e)
            raise ViomiSEException(f"Unable to connect to the device: {e}") from e

    def update(self):
        """
        Fetch all properties from the device using raw_command, update the internal state,
        and perform smart logic like auto-correcting the mop mode.
        This is a blocking call.
        """
        try:
            # This mapping structure is required for the 'get_properties' raw_command
            mapping = [
                {"did": p["did"], "siid": p["siid"], "piid": p["piid"]} for p in ALL_PROPS
            ]
            
            # The device has a limit on how many properties can be fetched at once.
            # We split the request into two parts, using the original logic.
            props_part1 = self._device.raw_command('get_properties', mapping[:12])
            props_part2 = self._device.raw_command('get_properties', mapping[12:])
            
            properties = props_part1 + props_part2

            # Process the response, which is a list of dictionaries.
            # Create a dictionary of results for easy access, keyed by "siid-piid".
            results_dict = {f"{p['siid']}-{p['piid']}": p for p in properties if 'siid' in p and 'piid' in p}

            # Build the final state dictionary in the correct order, handling potential errors.
            final_state = {}
            for prop_def in ALL_PROPS:
                key = f"{prop_def['siid']}-{prop_def['piid']}"
                result_prop = results_dict.get(key)
                
                if result_prop and result_prop.get('code') == 0:
                    final_state[prop_def['did']] = result_prop['value']
                else:
                    final_state[prop_def['did']] = None # Property could not be fetched
                    _LOGGER.warning(
                        "Failed to get property %s (siid: %s, piid: %s). Result: %s",
                        prop_def['did'], prop_def['siid'], prop_def['piid'], result_prop
                    )

            self.vacuum_state = final_state
            _LOGGER.debug("State update for %s successful, raw state: %s", self.ip, self.vacuum_state)

            # --- Smart Mop Mode Correction Logic ---
            self._auto_correct_mop_mode()

        except DeviceException as exc:
            raise ViomiSEException(f"Error fetching device state: {exc}") from exc

    def _auto_correct_mop_mode(self):
        """Checks and corrects the vacuum's cleaning mode based on hardware status."""
        if not self.vacuum_state or self.vacuum_state.get("run_state") != 4:
            return

        box_type = self.vacuum_state.get("box_type")
        mop_attached = self.vacuum_state.get("mop_type") == 1
        current_mop_mode = self.vacuum_state.get("is_mop")
        
        # Determine the correct mode based on hardware
        correct_mop_mode = None
        if box_type == 2 and mop_attached: correct_mop_mode = 2
        elif box_type == 3 and not mop_attached: correct_mop_mode = 0
        elif box_type == 3 and mop_attached and current_mop_mode != 2: correct_mop_mode = 1
        elif box_type == 1: correct_mop_mode = 0

        # If the current mode is incorrect, send a command to fix it
        if correct_mop_mode is not None and correct_mop_mode != current_mop_mode:
            _LOGGER.info("Mop mode mismatch. Correcting from %s to %s.", current_mop_mode, correct_mop_mode)
            self._device.raw_command(
                "set_properties",
                [{"did": "is_mop", "siid": 2, "piid": 11, "value": correct_mop_mode}]
            )

    # --- Getters for Home Assistant entity ---
    def get_state(self) -> str | None:
        """Get the translated, human-readable state."""
        return STATE_MAPPING.get(self.vacuum_state.get("run_state"), "Unknown")

    def get_battery(self) -> int | None:
        """Get the battery level."""
        return self.vacuum_state.get("battery_life")

    def get_fan_speed(self) -> str | None:
        """Get the translated, human-readable fan speed."""
        return FAN_SPEED_MAPPING.get(self.vacuum_state.get("suction_grade"))

    def fan_speeds(self) -> List[str]:
        """Return the list of supported fan speeds."""
        return list(FAN_SPEED_MAPPING.values())

    # --- Commands to be called by Home Assistant entity ---
    # For this specific firmware, actions must be sent using raw_command
    # with the correct service and action IDs (siid, aiid).

    def start(self):
        """Start cleaning."""
        # action: siid=2, aiid=1
        return self._try_command("start_sweep", "action", {"did": "start-sweep", "siid": 2, "aiid": 1, "in": []})

    def pause(self):
        """Pause cleaning."""
        # action: siid=2, aiid=3
        return self._try_command("pause_sweeping", "action", {"did": "pause-sweeping", "siid": 2, "aiid": 3, "in": []})

    def stop(self):
        """Stop cleaning."""
        # action: siid=2, aiid=2
        return self._try_command("stop_sweeping", "action", {"did": "stop-sweeping", "siid": 2, "aiid": 2, "in": []})

    def home(self):
        """Return to base."""
        # action: siid=2, aiid=4
        return self._try_command("return_to_base", "action", {"did": "return-to-base", "siid": 2, "aiid": 4, "in": []})

    def find(self):
        """Locate the vacuum."""
        # The v19 spec does not have a standard 'find_device' action.
        # This is a common miio command that should make a sound.
        return self._try_command("find_device", "find_device", [])

    def set_fan_speed(self, fan_speed_name: str):
        """Set the fan speed by its name."""
        if (speed_code := FAN_SPEED_MAPPING_REVERSE.get(fan_speed_name)) is not None:
            # property: siid=2, piid=19
            # This is a 'set_properties' call, which usually returns a result,
            # so we don't use the _try_command wrapper here.
            return self._device.raw_command(
                "set_properties",
                [{"did": "fan-speed", "siid": 2, "piid": 19, "value": speed_code}]
            )

    def send_command(self, command: str, params: List | Dict | None = None):
        """
        Wrapper for sending raw miot spec commands.
        This allows advanced users to call any action by its siid and aiid.
        """
        _LOGGER.debug("send_command called with: command=%s, params=%s", command, params)
        # We wrap this in the timeout-ignoring helper as most custom commands will be actions.
        return self._try_command(command, command, params)


