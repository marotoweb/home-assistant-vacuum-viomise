"""Custom Component for Viomi SE vacuum robot in Home Assistant."""
import asyncio
from functools import partial

import logging
from datetime import timedelta

from miio import DeviceException, ViomiVacuum

import voluptuous as vol

from homeassistant.components.vacuum import (
    VacuumActivity,
    StateVacuumEntity,
    VacuumEntityFeature,
    DOMAIN as VACUUM_DOMAIN,
)

from homeassistant.const import (
    ATTR_ENTITY_ID,
    CONF_HOST,
    CONF_NAME,
    CONF_TOKEN,
    STATE_OFF,
    STATE_ON,
    Platform,
)

from .const import DOMAIN, DATA_KEY

from homeassistant.helpers import entity
from homeassistant.helpers import config_validation as cv

from homeassistant.helpers.config_validation import PLATFORM_SCHEMA

_LOGGER = logging.getLogger(__name__)

DEFAULT_NAME = "Viomi Robot Vacuum Cleaner SE V-RVCLM21A"
DATA_KEY = "vacuum.viomise"

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_HOST): cv.string,
        vol.Required(CONF_TOKEN): vol.All(str, vol.Length(min=32, max=32)),
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    },
    extra=vol.ALLOW_EXTRA,
)

SCAN_INTERVAL = timedelta(seconds=30)

STATE_CODE_TO_STATE = {
    0: VacuumActivity.IDLE,
    1: VacuumActivity.IDLE,
    2: VacuumActivity.PAUSED,
    3: VacuumActivity.RETURNING,
    4: VacuumActivity.DOCKED,
    5: VacuumActivity.CLEANING,
    6: VacuumActivity.CLEANING,
    7: VacuumActivity.CLEANING,
}

VACUUM_SERVICE_SCHEMA = vol.Schema(
    {vol.Optional(ATTR_ENTITY_ID): cv.comp_entity_ids})
SERVICE_CLEAN_ZONE = "vacuum_clean_zone"
SERVICE_GOTO = "vacuum_goto"
SERVICE_CLEAN_SEGMENT = "vacuum_clean_segment"
SERVICE_OBS_CLEAN_ZONE = "xiaomi_clean_zone"
SERVICE_CLEAN_POINT = "xiaomi_clean_point"
ATTR_ZONE_ARRAY = "zone"
ATTR_ZONE_REPEATER = "repeats"
ATTR_X_COORD = "x_coord"
ATTR_Y_COORD = "y_coord"
ATTR_SEGMENTS = "segments"
ATTR_POINT = "point"
SERVICE_SCHEMA_CLEAN_ZONE = VACUUM_SERVICE_SCHEMA.extend(
    {
        vol.Required(ATTR_ZONE_ARRAY): vol.All(
            list,
            [
                vol.ExactSequence(
                    [vol.Coerce(float), vol.Coerce(float), vol.Coerce(float), vol.Coerce(float)]
                )
            ],
        ),
        vol.Required(ATTR_ZONE_REPEATER): vol.All(
            vol.Coerce(int), vol.Clamp(min=1, max=3)
        ),
    }
)
SERVICE_SCHEMA_GOTO = VACUUM_SERVICE_SCHEMA.extend(
    {
        vol.Required(ATTR_X_COORD): vol.Coerce(float),
        vol.Required(ATTR_Y_COORD): vol.Coerce(float),
    }
)
SERVICE_SCHEMA_CLEAN_SEGMENT = VACUUM_SERVICE_SCHEMA.extend(
    {
        vol.Required(ATTR_SEGMENTS): vol.Any(
            vol.Coerce(int),
            [vol.Coerce(int)]
        ),
    }
)
SERVICE_SCHEMA_CLEAN_POINT = VACUUM_SERVICE_SCHEMA.extend(
    {
        vol.Required(ATTR_POINT): vol.All(
            vol.ExactSequence(
                [vol.Coerce(float), vol.Coerce(float)]
            )
        )
    }
)
SERVICE_TO_METHOD = {
    SERVICE_CLEAN_ZONE: {
        "method": "async_clean_zone",
        "schema": SERVICE_SCHEMA_CLEAN_ZONE,
    },
    SERVICE_GOTO: {
        "method": "async_goto",
        "schema": SERVICE_SCHEMA_GOTO,
    },
    SERVICE_CLEAN_SEGMENT: {
        "method": "async_clean_segment",
        "schema": SERVICE_SCHEMA_CLEAN_SEGMENT,
    },
    SERVICE_OBS_CLEAN_ZONE: {
        "method": "async_clean_zone",
        "schema": SERVICE_SCHEMA_CLEAN_ZONE,
    },
    SERVICE_CLEAN_POINT: {
        "method": "async_clean_point",
        "schema": SERVICE_SCHEMA_CLEAN_POINT,
    }
}

FAN_SPEEDS = {"Silent": 0, "Standard": 1, "Medium": 2, "Turbo": 3}


SUPPORT_XIAOMI = (
    VacuumEntityFeature.STATE
    | VacuumEntityFeature.PAUSE
    | VacuumEntityFeature.STOP
    | VacuumEntityFeature.RETURN_HOME
    | VacuumEntityFeature.FAN_SPEED
    | VacuumEntityFeature.LOCATE
    | VacuumEntityFeature.SEND_COMMAND
    | VacuumEntityFeature.BATTERY
    | VacuumEntityFeature.START
)


STATE_CODE_TO_STATE = {
    0: VacuumActivity.IDLE,      # Sleep
    1: VacuumActivity.IDLE,      # Idle
    2: VacuumActivity.PAUSED,    # Paused
    3: VacuumActivity.RETURNING, # Go Charging
    4: VacuumActivity.DOCKED,    # Charging
    5: VacuumActivity.CLEANING,  # Vacuum
    6: VacuumActivity.CLEANING,  # Vacuum & Mop
    7: VacuumActivity.CLEANING   # Mop only
}

ALL_PROPS = [
    "run_state",
    "mode",
    "err_state",
    "battary_life",
    "box_type",
    "mop_type",
    "s_time",
    "s_area",
    "suction_grade",
    "water_grade",
    "remember_map",
    "has_map",
    "is_mop",
    "has_newmap",
    "main_brush_percentage",
    "main_brush_left",
    "side_brush_percentage",
    "side_brush_left",
    "filter_percentage",
    "filter_left",
    "mop_percentage",
    "mop_left",
    "repeat_state",
    "mop_route"
]

VACUUM_CARD_PROPS_REFERENCES = {
    'cleaned_area': 's_area',
    'cleaning_time': 's_time'
}

async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up the Xiaomi vacuum platform from config entry."""
    host = config_entry.data[CONF_HOST]
    token = config_entry.data[CONF_TOKEN]
    name = config_entry.data[CONF_NAME]

    # Create handler
    _LOGGER.info("Initializing with host %s (token %s...)", host, token[:5])

    vacuum = ViomiVacuum(host, token, model="viomi.vacuum.v19")
    mirobo = MiroboVacuum2(name, vacuum)
    
    hass.data.setdefault(DATA_KEY, {})
    hass.data[DATA_KEY][host] = mirobo
    hass.data[DOMAIN][config_entry.entry_id] = mirobo
    async_add_entities([mirobo], update_before_add=True)

    async def async_service_handler(service):
        """Map services to methods on MiroboVacuum."""
        method = SERVICE_TO_METHOD.get(service.service)
        if not method:
            _LOGGER.error(f"Service {service.service} was called but is not registered")
            return

        params = {
            key: value for key, value in service.data.items() if key != ATTR_ENTITY_ID
        }
        entity_ids = service.data.get(ATTR_ENTITY_ID)

        target_vacuums = []
        if entity_ids:
            target_vacuums = [
                vac for vac in hass.data[DATA_KEY].values()
                if vac.entity_id in entity_ids
            ]
        else:
            target_vacuums = list(hass.data[DATA_KEY].values())

        update_tasks = []
        for vacuum in target_vacuums:
            try:
                await getattr(vacuum, method["method"])(**params)
            except AttributeError as err:
                _LOGGER.error("Method %s not found in vacuum: %s", method["method"], err)
                continue

        for vacuum in target_vacuums:
            update_tasks.append(vacuum.async_update_ha_state(True))

        if update_tasks:
            await asyncio.gather(*update_tasks)

    # Register services
    for vacuum_service in SERVICE_TO_METHOD:
        schema = SERVICE_TO_METHOD[vacuum_service].get("schema", VACUUM_SERVICE_SCHEMA)
        hass.services.async_register(
            VACUUM_DOMAIN,  # Register under the vacuum domain
            vacuum_service,
            async_service_handler,
            schema=schema,
        )

    return True

class MiroboVacuum2(StateVacuumEntity):
    """Representation of a Xiaomi Vacuum cleaner robot."""

    def __init__(self, name, vacuum):
        """Initialize the Xiaomi vacuum cleaner robot handler."""
        self._name = name
        self._vacuum = vacuum
        self._unique_id = f"{vacuum.ip}-{vacuum.token}"  # Create unique ID from IP and token
        self._last_clean_point = None
        self.vacuum_state = None
        self._available = False

    @property
    def unique_id(self) -> str:
        """Return a unique ID."""
        return self._unique_id

    @property
    def device_info(self):
        """Return device info for this vacuum."""
        return {
            "identifiers": {(DOMAIN, self._unique_id)},
            "name": self._name,
            "manufacturer": "Viomi",
            "model": "Vacuum cleaner V-RVCLM21A",
        }

    @property
    def name(self):
        """Return the name of the device."""
        return self._name
    
    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return bool(self.coordinator.data)
    

    @property
    def activity(self):
        """Return the activity of the vacuum using the VacuumActivity enum."""
        if self.vacuum_state is not None:
            return STATE_CODE_TO_STATE.get(int(self.vacuum_state['run_state']), VacuumActivity.IDLE)
        return VacuumActivity.IDLE
    

    @property
    def battery_level(self):
        """Return the battery level of the vacuum cleaner."""
        if self.vacuum_state is not None:
            return self.vacuum_state['battary_life']

    @property
    def fan_speed(self):
        """Return the fan speed of the vacuum cleaner."""
        if self.vacuum_state is not None:
            speed = self.vacuum_state['suction_grade']
            if speed in FAN_SPEEDS.values():
                return [
                    key for key,
                    value in FAN_SPEEDS.items() if value == speed][0]
            return speed

    @property
    def fan_speed_list(self):
        """Get the list of available fan speed steps of the vacuum cleaner."""
        return list(sorted(FAN_SPEEDS.keys(), key=lambda s: FAN_SPEEDS[s]))

    @property
    def extra_state_attributes(self):
        """Return the specific state attributes of this vacuum cleaner."""
        attrs = {}
        if self.vacuum_state is not None:
            attrs.update(self.vacuum_state)
            try:
                attrs['status'] = STATE_CODE_TO_STATE[int(
                    self.vacuum_state['run_state'])]
            except KeyError:
                return "Definition missing for state %s" % self.vacuum_state['run_state']
        return attrs

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return self._available

    @property
    def supported_features(self):
        """Flag vacuum cleaner robot features that are supported."""
        return SUPPORT_XIAOMI

    async def _try_command(self, mask_error, func, *args, **kwargs):
        """Call a vacuum command handling error messages."""
        try:
            await self.hass.async_add_executor_job(partial(func, *args, **kwargs))
            return True
        except DeviceException as exc:
            _LOGGER.error(mask_error, exc)
            return False

    async def async_start(self):
        """Start or resume the cleaning task."""
        mode = self.vacuum_state['mode']
        is_mop = self.vacuum_state['is_mop']
        actionMode = 0

        if mode == 4 and self._last_clean_point is not None:
            method = 'set_pointclean'
            param = [1, self._last_clean_point[0], self._last_clean_point[1]]
        else:
            if mode == 2:
                actionMode = 2
            else:
                if is_mop == 2:
                    actionMode = 3
                else:
                    actionMode = is_mop
            if mode == 3:
                method = 'set_mode'
                param = [3, 1]
            else:
                method = 'set_mode_withroom'
                param = [actionMode, 1, 0]
        await self._try_command("Unable to start the vacuum: %s", self._vacuum.raw_command, method, param)

    async def async_pause(self):
        """Pause the cleaning task."""
        mode = self.vacuum_state['mode']
        is_mop = self.vacuum_state['is_mop']
        actionMode = 0

        if mode == 4 and self._last_clean_point is not None:
            method = 'set_pointclean'
            param = [3, self._last_clean_point[0], self._last_clean_point[1]]
        else:
            if mode == 2:
                actionMode = 2
            else:
                if is_mop == 2:
                    actionMode = 3
                else:
                    actionMode = is_mop
            if mode == 3:
                method = 'set_mode'
                param = [3, 3]
            else:
                method = 'set_mode_withroom'
                param = [actionMode, 3, 0]
        await self._try_command("Unable to set pause: %s", self._vacuum.raw_command, method, param)

    async def async_stop(self, **kwargs):
        """Stop the vacuum cleaner."""
        mode = self.vacuum_state['mode']
        if mode == 3:
            method = 'set_mode'
            param = [3, 0]
        elif mode == 4:
            method = 'set_pointclean'
            param = [0, 0, 0]
            self._last_clean_point = None
        else:
            method = 'set_mode'
            param = [0]
        await self._try_command("Unable to stop: %s", self._vacuum.raw_command, method, param)

    async def async_set_fan_speed(self, fan_speed, **kwargs):
        """Set fan speed."""
        if fan_speed.capitalize() in FAN_SPEEDS:
            fan_speed = FAN_SPEEDS[fan_speed.capitalize()]
        else:
            try:
                fan_speed = int(fan_speed)
            except ValueError as exc:
                _LOGGER.error(
                    "Fan speed step not recognized (%s). "
                    "Valid speeds are: %s", exc, self.fan_speed_list, )
                return
        await self._try_command(
            "Unable to set fan speed: %s", self._vacuum.raw_command, 'set_suction', [
                fan_speed]
        )

    async def async_return_to_base(self, **kwargs):
        """Set the vacuum cleaner to return to the dock."""
        await self._try_command("Unable to return home: %s", self._vacuum.raw_command, 'set_charge', [1])

    async def async_locate(self, **kwargs):
        """Locate the vacuum cleaner."""
        await self._try_command("Unable to locate the botvac: %s", self._vacuum.raw_command, 'set_resetpos', [1])

    async def async_send_command(self, command, params=None, **kwargs):
        # Home Assistant templating always returns a string, even if array is outputted, fix this so we can use templating in scripts.
        if isinstance(params, list) and len(params) == 1 and isinstance(params[0], str):
            if params[0].find('[') > -1 and params[0].find(']') > -1:
                params = eval(params[0])
            elif params[0].isnumeric():
                params[0] = int(params[0])

        """Send raw command."""
        await self._try_command(
            "Unable to send command to the vacuum: %s",
            self._vacuum.raw_command,
            command,
            params,
        )
        # self.update()
        
    async def _async_update_data(self):
        """Fetch state from the vacuum, handling errors gracefully."""
        try:
            data = await self.hass.async_add_executor_job(self.vacuum.status)
            if not data:
                raise DeviceException("No data received from vacuum")
            return data
        except OSError as exc:
            _LOGGER.error("Network error while fetching the vacuum state: %s", exc)
            return {}
        except DeviceException as exc:
            if "Unable to discover the device" in str(exc):
                _LOGGER.error("Viomi SE offline ou IP incorreto: %s", exc)
            else:
                _LOGGER.warning("Got exception while fetching the state: %s", exc)
            return {}

    def update(self):
        """Fetch state from the device."""
        try:
            state = self._vacuum.raw_command('get_prop', ALL_PROPS)

            mapping = [
                {"did":"run_state","siid":2,"piid":1},
                {"did":"mode","siid":2,"piid":18},
                {"did":"err_state","siid":2,"piid":2},
                {"did":"battery_life","siid":3,"piid":1},
                {"did":"box_type","siid":2,"piid":12},
                {"did":"mop_type","siid":2,"piid":13},
                {"did":"s_time","siid":2,"piid":15},
                {"did":"s_area","siid":2,"piid":16},
                {"did":"suction_grade","siid":2,"piid":19},
                {"did":"water_grade","siid":4,"piid":18,},
                {"did":"remember_map","siid":4,"piid":3},
                {"did":"has_map","siid":4,"piid":4},
                {"did":"is_mop","siid":2,"piid":11},
                {"did":"has_newmap","siid":4,"piid":5},
                {"did":"main_brush_left_percentage","siid":4,"piid":10},
                {"did":"main_brush","siid":4,"piid":11,},
                {"did":"side_brush_left_percentage","siid":4,"piid":8},
                {"did":"side_brush_left","siid":4,"piid":9},
                {"did":"filter_left_percentage","siid":4,"piid":12},
                {"did":"filter_left","siid":4,"piid":13},
                {"did":"mop_left_percentage","siid":4,"piid":14},
                {"did":"mop_left","siid":4,"piid":15},
                {"did":"repeat_state","siid":4,"piid":1},
                {"did":"mop_route","siid":4,"piid":6}
                ]
            
            # Respect the maximum
            properties = self._vacuum.raw_command('get_properties', mapping[:12])
            properties.extend(self._vacuum.raw_command('get_properties', mapping[12:]))

            state = []
            for d in properties:
                state.append(d['value'])

            self.vacuum_state = dict(zip(ALL_PROPS, state))

            self._available = True

            # Automatically set mop based on box_type
            # For ViomiSE
            # mop_type: 0=NoMop, 1=MopAttached
            # box_type: 0=NoBox, 1=DustBox, 2=WhaterBox, 3=2in1Box
            # is_mop: 0=Vacuum, 1=Vacuum&Mop, 2=Mop

            mop_type = bool(self.vacuum_state['mop_type'])
            box_type = int(self.vacuum_state['box_type'])
            is_mop = int(self.vacuum_state['is_mop'])
            run_state = int(self.vacuum_state['run_state'])

            if run_state == 4:
                update_mop = None
                if box_type == 2 and mop_type:
                    update_mop = 2 #Mop only
                elif box_type == 3 and not mop_type:
                    update_mop = 0 #Vacuum
                elif box_type == 3 and mop_type and is_mop != 2:
                    update_mop = 1 #Vacum&Mop
                elif box_type == 1:
                    update_mop = 0 #Vacuum only

                if update_mop is not None and update_mop != is_mop:
                    self._vacuum.raw_command('set_mop', [update_mop])
                    self.update()
                
        except OSError as exc:
            _LOGGER.error("Got OSError while fetching the state: %s", exc)
        except DeviceException as exc:
            _LOGGER.warning("Got exception while fetching the state: %s", exc)


    async def async_clean_zone(self, zone, repeats=1):
        """Clean selected area for the number of repeats indicated."""
        result = []
        i = 0
        for z in zone:
            x1, y2, x2, y1 = z
            res = '_'.join(str(x)
            for x in [i, 0, x1, y1, x1, y2, x2, y2, x2, y1])
            for _ in range(repeats):
                result.append(res)
                i += 1
        result = [i] + result

        await self._try_command("Unable to clean zone: %s", self._vacuum.raw_command, 'set_uploadmap', [1]) \
            and await self._try_command("Unable to clean zone: %s", self._vacuum.raw_command, 'set_zone', result) \
            and await self._try_command("Unable to clean zone: %s", self._vacuum.raw_command, 'set_mode', [3, 1])

    async def async_goto(self, x_coord, y_coord):
        """Clean area around the specified coordinates"""
        self._last_clean_point = [x_coord, y_coord]
        await self._try_command("Unable to goto: %s", self._vacuum.raw_command, 'set_uploadmap', [0]) \
            and await self._try_command("Unable to goto: %s", self._vacuum.raw_command, 'set_pointclean', [1, x_coord, y_coord])

    async def async_clean_segment(self, segments):
        """Clean selected segment(s) (rooms)"""
        if isinstance(segments, int):
            segments = [segments]

        await self._try_command("Unable to clean segments: %s", self._vacuum.raw_command, 'set_uploadmap', [1]) \
            and await self._try_command("Unable to clean segments: %s", self._vacuum.raw_command, 'set_mode_withroom', [0, 1, len(segments)] + segments)

    async def async_clean_point(self, point):
        """Clean selected area"""
        x, y = point
        self._last_clean_point = point
        await self._try_command("Unable to clean point: %s", self._vacuum.raw_command, 'set_uploadmap', [0]) \
            and await self._try_command("Unable to clean point: %s", self._vacuum.raw_command, 'set_pointclean', [1, x, y])
