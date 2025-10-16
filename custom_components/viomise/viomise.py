"""
The smart core for the Viomi v19 integration.
This file contains the ViomiSE class, which handles all direct communication
with the vacuum, state parsing, and business logic.
"""
import logging
from typing import Any, Dict, List

# We only import the basic exceptions at the top level to avoid blocking I/O
from miio import DeviceException

_LOGGER = logging.getLogger(__name__)

# Custom Exception for better error handling
class ViomiSEException(Exception):
    """Base exception for Viomi SE device errors."""
    pass

# ... (ALL_PROPS_MAP, STATE_MAPPING, etc. continuam aqui como antes) ...
ALL_PROPS_MAP = [
    {"did": "run_state", "siid": 2, "piid": 1},
    {"did": "mode", "siid": 2, "piid": 18},
    {"did": "err_state", "siid": 2, "piid": 2},
    {"did": "battary_life", "siid": 3, "piid": 1},
    {"did": "box_type", "siid": 2, "piid": 12},
    {"did": "mop_type", "siid": 2, "piid": 13},
    {"did": "s_time", "siid": 2, "piid": 15},
    {"did": "s_area", "siid": 2, "piid": 16},
    {"did": "suction_grade", "siid": 2, "piid": 19},
    {"did": "water_grade", "siid": 4, "piid": 18},
    {"did": "remember_map", "siid": 4, "piid": 3},
    {"did": "has_map", "siid": 4, "piid": 4},
    {"did": "is_mop", "siid": 2, "piid": 11},
    {"did": "has_newmap", "siid": 4, "piid": 5},
    {"did": "main_brush_left_percentage", "siid": 4, "piid": 10},
    {"did": "main_brush_left", "siid": 4, "piid": 11},
    {"did": "side_brush_left_percentage", "siid": 4, "piid": 8},
    {"did": "side_brush_left", "siid": 4, "piid": 9},
    {"did": "filter_left_percentage", "siid": 4, "piid": 12},
    {"did": "filter_left", "siid": 4, "piid": 13},
    {"did": "mop_left_percentage", "siid": 4, "piid": 14},
    {"did": "mop_left", "siid": 4, "piid": 15},
    {"did": "repeat_state", "siid": 4, "piid": 1},
    {"did": "mop_route", "siid": 4, "piid": 6}
]
ALL_PROPS_DID_NAMES = [p["did"] for p in ALL_PROPS_MAP]

STATE_MAPPING = {
    0: "Sleeping", 1: "Idle", 2: "Paused", 3: "Returning to base",
    4: "Charging", 5: "Cleaning", 6: "Cleaning and Mopping", 7: "Mopping",
}
FAN_SPEEDS = {"Silent": 0, "Standard": 1, "Medium": 2, "Turbo": 3}
FAN_SPEEDS_REVERSE = {v: k for k, v in FAN_SPEEDS.items()}


class ViomiSE:
    """
    Main class for handling communication with the Viomi v19 vacuum.
    """
    def __init__(self, ip: str, token: str):
        """Initialize the device communication handler."""
        _LOGGER.debug("Initializing ViomiSE handler for IP: %s", ip)
        self.ip = ip
        self.token = token
        
        # === LAZY IMPORT ===
        # Import MiotDevice here to avoid blocking Home Assistant startup
        from miio.miot_device import MiotDevice
        
        self._device = MiotDevice(ip, token, mapping={})
        self.vacuum_state: Dict[str, Any] = {}
        self._last_clean_point = None
        self.info = None

    def connect(self) -> bool:
        """Establish connection to the device and get basic info."""
        try:
            self.info = self._device.info()
            _LOGGER.debug("Successfully connected to device %s. Model: %s", self.ip, self.info.model)
            return True
        except DeviceException as e:
            _LOGGER.error("Failed to connect to device %s: %s", self.ip, e)
            raise ViomiSEException(f"Unable to connect to the device: {e}") from e

    # ... (o resto do código, a partir do método "update", é exatamente igual ao da mensagem anterior) ...
    def update(self):
        """Fetch all properties from the device using the original logic."""
        try:
            props_part1 = self._device.raw_command('get_properties', ALL_PROPS_MAP[:12])
            props_part2 = self._device.raw_command('get_properties', ALL_PROPS_MAP[12:])
            properties = props_part1 + props_part2

            prop_values = {f"{p['siid']}-{p['piid']}": p.get('value') for p in properties if p.get('code') == 0}

            state = {}
            for prop_def in ALL_PROPS_MAP:
                key = f"{prop_def['siid']}-{prop_def['piid']}"
                state[prop_def['did']] = prop_values.get(key)
            
            self.vacuum_state = state
            _LOGGER.debug("State update successful, raw state: %s", self.vacuum_state)

            self._auto_correct_mop_mode()

        except DeviceException as exc:
            _LOGGER.warning("Got exception while fetching the state: %s", exc)
            raise ViomiSEException(f"Error fetching device state: {exc}") from exc
        except Exception as exc:
            _LOGGER.error("Got an unexpected error while fetching the state: %s", exc)
            raise ViomiSEException(f"Unexpected error fetching state: {exc}") from exc

    def _auto_correct_mop_mode(self):
        """Checks and corrects the vacuum's cleaning mode based on hardware status."""
        if not self.vacuum_state or self.vacuum_state.get("run_state") != 4:
            return

        try:
            mop_type = bool(self.vacuum_state.get('mop_type'))
            box_type = int(self.vacuum_state.get('box_type'))
            is_mop = int(self.vacuum_state.get('is_mop'))

            update_mop = None
            if box_type == 2 and mop_type: update_mop = 2
            elif box_type == 3 and not mop_type: update_mop = 0
            elif box_type == 3 and mop_type and is_mop != 2: update_mop = 1
            elif box_type == 1: update_mop = 0

            if update_mop is not None and update_mop != is_mop:
                _LOGGER.info("Mop mode mismatch. Correcting from %s to %s.", is_mop, update_mop)
                self._device.raw_command('set_mop', [update_mop])
                self.update()
        except (TypeError, ValueError) as e:
            _LOGGER.warning("Could not perform mop auto-correction, state values might be None: %s", e)

    def _try_command(self, description: str, func, *args, **kwargs):
        """Call a vacuum command handling the expected timeout for actions."""
        try:
            func(*args, **kwargs)
            return True
        except DeviceException as exc:
            _LOGGER.warning("%s: %s. This is often normal for this model.", description, exc)
            return True

    def get_state(self) -> str | None:
        if self.vacuum_state:
            state_code = self.vacuum_state.get("run_state")
            return STATE_MAPPING.get(state_code, "Unknown")
        return "Unknown"

    def get_battery(self) -> int | None:
        return self.vacuum_state.get("battary_life")

    def get_fan_speed(self) -> str | None:
        if self.vacuum_state:
            speed_code = self.vacuum_state.get('suction_grade')
            return FAN_SPEEDS_REVERSE.get(speed_code)
        return None

    def fan_speeds(self) -> List[str]:
        return list(FAN_SPEEDS.keys())

    def start(self):
        mode = self.vacuum_state.get('mode')
        is_mop = self.vacuum_state.get('is_mop')
        
        if mode == 4 and self._last_clean_point is not None:
            method, param = 'set_pointclean', [1, self._last_clean_point[0], self._last_clean_point[1]]
        else:
            actionMode = 0
            if mode == 2: actionMode = 2
            else:
                if is_mop == 2: actionMode = 3
                else: actionMode = is_mop
            
            if mode == 3:
                method, param = 'set_mode', [3, 1]
            else:
                method, param = 'set_mode_withroom', [actionMode, 1, 0]
        
        return self._try_command("Unable to start the vacuum", self._device.raw_command, method, param)

    def pause(self):
        mode = self.vacuum_state.get('mode')
        is_mop = self.vacuum_state.get('is_mop')

        if mode == 4 and self._last_clean_point is not None:
            method, param = 'set_pointclean', [3, self._last_clean_point[0], self._last_clean_point[1]]
        else:
            actionMode = 0
            if mode == 2: actionMode = 2
            else:
                if is_mop == 2: actionMode = 3
                else: actionMode = is_mop
            
            if mode == 3:
                method, param = 'set_mode', [3, 3]
            else:
                method, param = 'set_mode_withroom', [actionMode, 3, 0]
        
        return self._try_command("Unable to set pause", self._device.raw_command, method, param)

    def stop(self):
        mode = self.vacuum_state.get('mode')
        if mode == 3:
            method, param = 'set_mode', [3, 0]
        elif mode == 4:
            method, param = 'set_pointclean', [0, 0, 0]
            self._last_clean_point = None
        else:
            method, param = 'set_mode', [0]
        
        return self._try_command("Unable to stop", self._device.raw_command, method, param)

    def home(self):
        return self._try_command("Unable to return home", self._device.raw_command, 'set_charge', [1])

    def find(self):
        return self._try_command("Unable to locate the botvac", self._device.raw_command, 'set_resetpos', [1])

    def set_fan_speed(self, fan_speed_name: str):
        if (speed_code := FAN_SPEEDS.get(fan_speed_name)) is not None:
            return self._try_command(
                "Unable to set fan speed", self._device.raw_command, 'set_suction', [speed_code]
            )

    def send_command(self, command: str, params: Any = None):
        return self._try_command(
            f"Unable to send command {command}", self._device.raw_command, command, params
        )

    def clean_zone(self, zone, repeats=1):
        result = []
        i = 0
        for z in zone:
            x1, y2, x2, y1 = z
            res = '_'.join(str(x) for x in [i, 0, x1, y1, x1, y2, x2, y2, x2, y1])
            for _ in range(repeats):
                result.append(res)
                i += 1
        result = [i] + result

        self._try_command("Unable to clean zone (uploadmap)", self._device.raw_command, 'set_uploadmap', [1])
        self._try_command("Unable to clean zone (set_zone)", self._device.raw_command, 'set_zone', result)
        self._try_command("Unable to clean zone (set_mode)", self._device.raw_command, 'set_mode', [3, 1])

    def clean_point(self, point):
        x, y = point
        self._last_clean_point = point
        self._try_command("Unable to clean point (uploadmap)", self._device.raw_command, 'set_uploadmap', [0])
        self._try_command("Unable to clean point (set_pointclean)", self._device.raw_command, 'set_pointclean', [1, x, y])

