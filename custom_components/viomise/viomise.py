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
        Fetch all properties from the device, update the internal state,
        and perform smart logic like auto-correcting the mop mode.
        This is a blocking call.
        """
        try:
            prop_names = [p["did"] for p in ALL_PROPS]
            
            # The device has a limit on how many properties can be fetched at once.
            # We split the request into two parts.
            props_part1 = self._device.get_properties(ALL_PROPS[:12])
            props_part2 = self._device.get_properties(ALL_PROPS[12:])
            
            all_props_values = props_part1 + props_part2
            
            self.vacuum_state = dict(zip(prop_names, all_props_values))
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
            self._device.send("set_mop", [correct_mop_mode])

    # --- Getters for Home Assistant entity ---
    def get_state(self) -> str | None:
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
    def start(self): self._device.send("start_sweep", [])
    def pause(self): self._device.send("pause_sweeping", [])
    def stop(self): self._device.send("stop_sweeping", [])
    def home(self): self._device.send("start_charge", [])
    def find(self): self._device.send("find_device", [])

    def set_fan_speed(self, fan_speed_name: str):
        if (speed_code := FAN_SPEED_MAPPING_REVERSE.get(fan_speed_name)) is not None:
            self._device.send("set_suction", [speed_code])

    def send_command(self, command: str, params: List | Dict | None = None):
        """Wrapper for sending custom or specific commands."""
        if command == "set_room_clean":
            self._device.send("set_room_clean", params)
        else:
            self._device.send(command, params)

