"""HASP components module."""
import json
import logging

from homeassistant.components import mqtt
from homeassistant.const import ATTR_ENTITY_ID, SERVICE_TURN_OFF, SERVICE_TURN_ON
from homeassistant.core import DOMAIN as HA_DOMAIN, callback
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity_component import EntityComponent
from homeassistant.helpers.event import async_track_state_change_event
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.helpers.service import async_call_from_config
from homeassistant.setup import async_when_setup
import voluptuous as vol

from .const import (
    ATTR_CURRENT_DIM,
    CONF_AWAKE_BRIGHTNESS,
    CONF_ENTITY,
    CONF_EVENT,
    CONF_IDLE_BRIGHTNESS,
    CONF_OBJECTS,
    CONF_OBJID,
    CONF_PAGES,
    CONF_PAGES_HOME,
    CONF_PAGES_NEXT,
    CONF_PAGES_PREV,
    CONF_TOPIC,
    CONF_TRACK,
    DATA_ENTITY_MAP,
    DATA_IDLE,
    DATA_PAGE_ENTITY,
    DATA_PLATE_TOPIC,
    DATA_SERVICE_MAP,
    DEFAULT_AWAKE_BRIGHNESS,
    DEFAULT_IDLE_BRIGHNESS,
    DOMAIN,
    HASP_EVENT,
    HASP_EVENT_DOWN,
    HASP_EVENTS,
    HASP_HOME_PAGE,
    HASP_IDLE_LONG,
    HASP_IDLE_OFF,
    HASP_IDLE_SHORT,
    HASP_IDLE_STATES,
    HASP_VAL,
    TOGGLE,
    ALARM,
)

_LOGGER = logging.getLogger(__name__)


# Configuration YAML schemas
EVENT_SCHEMA = cv.schema_with_slug_keys(cv.SERVICE_SCHEMA)

OBJECT_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_OBJID): cv.string,
        vol.Optional(CONF_TRACK, default=None): vol.Any(cv.entity_id, None),
        vol.Optional(CONF_EVENT, default={}): EVENT_SCHEMA,
    }
)

PAGES_SCHEMA = vol.Schema(
    {
        vol.Optional(CONF_PAGES_PREV): cv.string,
        vol.Optional(CONF_PAGES_HOME): cv.string,
        vol.Required(CONF_PAGES_NEXT): cv.string,
    }
)

PLATE_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_OBJECTS): vol.All(cv.ensure_list, [OBJECT_SCHEMA]),
        vol.Required(CONF_PAGES): PAGES_SCHEMA,
        vol.Required(CONF_TOPIC): mqtt.valid_subscribe_topic,
        vol.Optional(CONF_AWAKE_BRIGHTNESS, default=DEFAULT_AWAKE_BRIGHNESS): vol.All(
            int, vol.Range(min=0, max=100)
        ),
        vol.Optional(CONF_IDLE_BRIGHTNESS, default=DEFAULT_IDLE_BRIGHNESS): vol.All(
            int, vol.Range(min=0, max=100)
        ),
    },
    extra=vol.ALLOW_EXTRA,
)

CONFIG_SCHEMA = vol.Schema(
    {DOMAIN: vol.Schema({cv.slug: PLATE_SCHEMA})}, extra=vol.ALLOW_EXTRA
)

# JSON Messages from HASP schemas
HASP_VAL_SCHEMA = vol.Schema(
    {vol.Required(HASP_VAL): vol.All(int, vol.Range(min=0, max=1))},
    extra=vol.ALLOW_EXTRA,
)
HASP_EVENT_SCHEMA = vol.Schema(
    {vol.Required(HASP_EVENT): vol.Any(*HASP_EVENTS)}, extra=vol.ALLOW_EXTRA
)

HASP_IDLE_SCHEMA = vol.Schema(vol.Any(*HASP_IDLE_STATES))


def update_object_state(hass, entity_id, value):
    # cast state values off/on to 0/1
    if value in TOGGLE:
        value = TOGGLE.index(value)
    # cast alarm_panel values to 0/1
    if value in ALARM:
        value = 1 if ALARM.index(value) > 9 else 0

    for command_topic in hass.data[DOMAIN][DATA_ENTITY_MAP][entity_id]:
        #_LOGGER.debug("_update_hasp_obj(%s) = %s", command_topic, value)
        hass.components.mqtt.async_publish(command_topic, value)

async def async_listen_state_changes(hass, entity_id, plate, obj):
    """Listen to state changes."""
    command_topic = f"{hass.data[DOMAIN][plate][DATA_PLATE_TOPIC]}/command/{obj}.val"
    state_topic = f"{hass.data[DOMAIN][plate][DATA_PLATE_TOPIC]}/state/{obj}"

    if hass.data[DOMAIN][DATA_ENTITY_MAP].get(entity_id) is None:
        hass.data[DOMAIN][DATA_ENTITY_MAP][entity_id] = []
    hass.data[DOMAIN][DATA_ENTITY_MAP][entity_id].append(command_topic)

    hass.data[DOMAIN][DATA_SERVICE_MAP][state_topic] = entity_id

    _LOGGER.debug("Track Entity: %s -> %s", entity_id, command_topic)

    @callback
    def _update_hasp_obj(event):
        entity_id = event.data.get("entity_id")
        value = event.data.get("new_state").state

        update_object_state(hass, entity_id, value)

    async_track_state_change_event(hass, entity_id, _update_hasp_obj)
    current_state = hass.states.get(entity_id)
    if current_state:
        value = current_state.state

        update_object_state(hass, entity_id, value)

    @callback
    async def message_received(msg):
        """Process MQTT message from plate."""
        entity_id = hass.data[DOMAIN][DATA_SERVICE_MAP][msg.topic]

        m = HASP_VAL_SCHEMA(json.loads(msg.payload))
        if m[HASP_VAL] == 1:
            service = SERVICE_TURN_ON
        else:
            service = SERVICE_TURN_OFF

        _LOGGER.debug("_update_hasp_obj(%s) = %s", entity_id, service)
        await hass.services.async_call(
            HA_DOMAIN,
            service,
            {
                ATTR_ENTITY_ID: entity_id,
            },
        )

    domain = entity_id.split(".", 1)[0]
    if domain in ["switch", "light", "media_player"]:
        await hass.components.mqtt.async_subscribe(state_topic, message_received)


async def async_listen_hasp_events(hass, obj, plate, conf):
    """Listen to messages on MQTT for HASP events."""
    state_topic = f"{hass.data[DOMAIN][plate][DATA_PLATE_TOPIC]}/state/{obj}"
    hass.data[DOMAIN][DATA_SERVICE_MAP][state_topic] = conf

    @callback
    async def message_received(msg):
        """Process MQTT message from plate."""
        conf = hass.data[DOMAIN][DATA_SERVICE_MAP][msg.topic]
        try:
            m = HASP_EVENT_SCHEMA(json.loads(msg.payload))

            for event in conf:
                if event in m[HASP_EVENT]:
                    _LOGGER.debug(
                        "Service call for %s triggered by %s on %s",
                        event,
                        msg.payload,
                        msg.topic,
                    )
                    await async_call_from_config(
                        hass, conf[event], validate_config=True
                    )
        except vol.error.Invalid as err:
            _LOGGER.warning("Could not handle event %s on %s", msg.payload, msg.topic)

    _LOGGER.debug("Subscribe for %s events on %s", obj, state_topic)
    await hass.components.mqtt.async_subscribe(state_topic, message_received)


async def async_setup(hass, config):
    """Set up the MQTT async example component."""
    component = EntityComponent(_LOGGER, DOMAIN, hass)

    hass.data[DOMAIN] = {
        DATA_SERVICE_MAP: {},
        DATA_ENTITY_MAP: {},
    }

    for plate in config[DOMAIN]:
        hass.data[DOMAIN][plate] = {
            DATA_PLATE_TOPIC: config[DOMAIN][plate][CONF_TOPIC],
        }

        await component.async_add_entities([Panel(plate, config[DOMAIN][plate])])

        # Setup remaining objects
        for obj in config[DOMAIN][plate][CONF_OBJECTS]:
            objid = obj[CONF_OBJID]

            track_entity_id = obj.get(CONF_TRACK)
            if track_entity_id:
                await async_listen_state_changes(hass, track_entity_id, plate, objid)

            event_services = obj.get(CONF_EVENT)
            if event_services:
                _LOGGER.debug("Setup event_services for %s", obj[CONF_OBJID])
                await async_listen_hasp_events(hass, objid, plate, event_services)

    return True


class Panel(RestoreEntity):
    """Representation of an HASP-LVGL."""

    def __init__(self, name, config):
        """Initialize a panel."""
        self._name = name
        self._topic = config[CONF_TOPIC]
        self._awake_brightness = config[CONF_AWAKE_BRIGHTNESS]
        self._idle_brightness = config[CONF_IDLE_BRIGHTNESS]
        self._home_btn = config[CONF_PAGES][CONF_PAGES_HOME]
        self._prev_btn = config[CONF_PAGES][CONF_PAGES_PREV]
        self._next_btn = config[CONF_PAGES][CONF_PAGES_NEXT]

        self._page = 1
        self._dim = 0
        self._backlight = 1

    async def async_added_to_hass(self):
        """Run when entity about to be added."""
        await super().async_added_to_hass()

        state = await self.async_get_last_state()
        if state:
            self._page = int(state.state)
            self._dim = int(state.attributes.get(ATTR_CURRENT_DIM))
            _LOGGER.debug("Restore DIM to %s", self._dim)

        await self.async_listen_idleness()
        await self.async_setup_pages()

    @property
    def name(self):
        """Return the name of the select input."""
        return self._name

    @property
    def icon(self):
        """Return the icon to be used for this entity."""
        return "mdi:light-switch"

    @property
    def state(self):
        """Return the state of the component."""
        return self._page

    @property
    def state_attributes(self):
        """Return the state attributes."""
        return {ATTR_CURRENT_DIM: self._dim}

    async def async_listen_idleness(self):
        """Listen to messages on MQTT for HASP idleness."""
        state_topic = f"{self._topic}/state/idle"
        dim_topic = f"{self._topic}/command/dim"
        backlight_topic = f"{self._topic}/command/light"

        # Sync state on boot
        self.hass.components.mqtt.async_publish(dim_topic, self._dim, qos=0, retain=False)
        self.hass.components.mqtt.async_publish(backlight_topic, self._backlight, qos=0, retain=False)

        @callback
        async def idle_message_received(msg):
            """Process MQTT message from plate."""
            m = HASP_IDLE_SCHEMA(msg.payload)

            if m == HASP_IDLE_OFF:
                self._dim = self._awake_brightness
                self._backlight = 1
            elif m == HASP_IDLE_SHORT:
                self._dim = self._idle_brightness
                self._backlight = 1
            elif m == HASP_IDLE_LONG:
                self._dim = self._awake_brightness
                self._backlight = 0

            _LOGGER.debug("Idle state is %s - Dimming %s to %s; Backlight %s to %s", msg.payload, dim_topic, self._dim, backlight_topic, self._backlight)
            self.hass.components.mqtt.async_publish(backlight_topic, self._backlight, qos=0, retain=False)
            self.hass.components.mqtt.async_publish(dim_topic, self._dim, qos=0, retain=False)
            self.async_write_ha_state()

        await self.hass.components.mqtt.async_subscribe(
            state_topic, idle_message_received
        )

    async def async_setup_pages(self):
        """Listen to messages on MQTT for HASP Page changes."""
        cmd_topic = f"{self._topic}/command/page"

        async def page_message_received(msg):
            """Process MQTT message from plate."""
            _LOGGER.debug("page button received: %s ", msg.topic)

            # Parse received JSON
            cmd = HASP_EVENT_SCHEMA(json.loads(msg.payload))
            if cmd[HASP_EVENT] != HASP_EVENT_DOWN:
                return

            if msg.topic.endswith(self._prev_btn):
                self._page -= 1
            if msg.topic.endswith(self._home_btn):
                self._page = HASP_HOME_PAGE
            if msg.topic.endswith(self._next_btn):
                self._page += 1

            _LOGGER.debug("Change page %s to %s", cmd_topic, self._page)
            self.hass.components.mqtt.async_publish(
                cmd_topic, self._page, qos=0, retain=False
            )
            self.async_write_ha_state()

        for obj in [self._prev_btn, self._home_btn, self._next_btn]:
            if obj is None:
                continue

            state_topic = f"{self._topic}/state/{obj}"
            _LOGGER.debug("Track page button: %s -> %s", obj, state_topic)
            await self.hass.components.mqtt.async_subscribe(state_topic, page_message_received)
