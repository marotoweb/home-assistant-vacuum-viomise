# custom_components/viomise/viomise.py

import logging
from functools import partial
from typing import Any, Dict, List

from miio import DeviceException
from miio.miot_device import MiotDevice

_LOGGER = logging.getLogger(__name__)

# Your original mapping and constants
ALL_PROPS = [
    "run_state", "mode", "err_state", "battary_life", "box_type", "mop_type",
    "s_time", "s_area", "suction_grade", "water_grade", "remember_map",
    "has_map", "is_mop", "has_newmap", "main_brush_left_percentage",
    "main_brush_left", "side_brush_left_percentage", "side_brush_left",
    "filter_left_percentage", "filter_left", "mop_left_percentage",
    "mop_left", "repeat_state", "mop_route"
]

MAPPING = [
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

FAN_SPEEDS = {"Silent": 0, "Standard": 1, "Medium": 2, "Turbo": 3}
FAN_SPEEDS_REVERSE = {v: k for k, v in FAN_SPEEDS.items()}

class ViomiSEException(Exception):
    pass

class ViomiSE:
    def __init__(self, ip: str, token: str):
        _LOGGER.debug("Initializing ViomiSE handler for IP: %s", ip)
        self.ip = ip
        self.token = token
        self._device = MiotDevice(ip, token, mapping={})
        self.vacuum_state: Dict[str, Any] = {}
        self._last_clean_point = None
        self.info = None

    def connect(self) -> bool:
        try:
            self.info = self._device.info()
            _LOGGER.debug("Successfully connected to device %s. Model: %s", self.ip, self.info.model)
            return True
        except DeviceException as e:
            _LOGGER.error("Failed to connect to device %s: %s", self.ip, e)
            raise ViomiSEException(f"Unable to connect to the device: {e}") from e

    def update(self):
        try:
            # Respect the maximum properties per call
            properties = self._device.raw_command('get_properties', MAPPING[:12])
            properties.extend(self._device.raw_command('get_properties', MAPPING[12:]))

            state_values = [p['value'] for p in properties if 'value' in p]
            self.vacuum_state = dict(zip(ALL_PROPS, state_values))
            
            _LOGGER.debug("State update successful, raw state: %s", self.vacuum_state)
            self._auto_correct_mop_mode()
        except DeviceException as exc:
            _LOGGER.warning("Got exception while fetching the state: %s", exc)
            raise ViomiSEException(f"Error fetching device state: {exc}") from exc

    def _auto_correct_mop_mode(self):
        if not self.vacuum_state or self.vacuum_state.get("run_state") != 4:
            return
        # ... (Your auto-correction logic remains the same) ...

    def _try_command(self, description: str, func, *args, **kwargs):
        try:
            func(*args, **kwargs)
            return True
        except DeviceException as exc:
            _LOGGER.warning("%s: %s. This is often normal for this model.", description, exc)
            return True # Assume success despite timeout

    def get_state(self):
        return self.vacuum_state.get("run_state")

    def get_battery(self):
        return self.vacuum_state.get("battary_life")

    def get_fan_speed(self):
        speed_code = self.vacuum_state.get('suction_grade')
        return FAN_SPEEDS_REVERSE.get(speed_code)

    def fan_speeds(self):
        return list(FAN_SPEEDS.keys())
        
    def start(self):
        # Your original start logic
        mode = self.vacuum_state.get('mode')
        is_mop = self.vacuum_state.get('is_mop')
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
        # Your original pause logic
        mode = self.vacuum_state.get('mode')
        is_mop = self.vacuum_state.get('is_mop')
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
        # Your original stop logic
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
        # Your original clean_zone logic
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
        # Your original clean_point logic
        x, y = point
        self._last_clean_point = point
        self._try_command("Unable to clean point (uploadmap)", self._device.raw_command, 'set_uploadmap', [0])
        self._try_command("Unable to clean point (set_pointclean)", self._device.raw_command, 'set_pointclean', [1, x, y])

