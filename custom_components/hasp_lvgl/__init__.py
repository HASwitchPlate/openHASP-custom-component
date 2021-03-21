"""HASP components module."""
import json
import logging

from homeassistant.components import mqtt
from homeassistant.core import callback, split_entity_id
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity_component import EntityComponent
from homeassistant.helpers.event import async_track_state_change_event
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.helpers.service import async_call_from_config
import voluptuous as vol

from .const import (
    ALARM,
    ATTR_CURRENT_DIM,
    CONF_AWAKE_BRIGHTNESS,
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


async def async_setup(hass, config):
    """Set up the MQTT async example component."""
    component = EntityComponent(_LOGGER, DOMAIN, hass)

    for plate in config[DOMAIN]:
        plate = SwitchPlate(hass, plate, config[DOMAIN][plate])

        await component.async_add_entities([plate])

    return True


class SwitchPlate(RestoreEntity):
    """Representation of an HASP-LVGL."""

    def __init__(self, hass, name, config):
        """Initialize a plate."""
        self._name = name
        self._topic = config[CONF_TOPIC]
        self._awake_brightness = config[CONF_AWAKE_BRIGHTNESS]
        self._idle_brightness = config[CONF_IDLE_BRIGHTNESS]
        self._home_btn = config[CONF_PAGES][CONF_PAGES_HOME]
        self._prev_btn = config[CONF_PAGES][CONF_PAGES_PREV]
        self._next_btn = config[CONF_PAGES][CONF_PAGES_NEXT]

        # Setup remaining objects
        self._objects = []
        for obj in config[CONF_OBJECTS]:
            new_obj = HASPObject(hass, self, obj)

            self.add_object(new_obj)

        self._page = 1
        self._dim = 0
        self._backlight = 1

    @property
    def topic(self):
        """SwitchPlate base topic."""
        return self._topic

    def add_object(self, obj):
        """Track objects in plate."""
        self._objects.append(obj)

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

        for obj in self._objects:
            await obj.async_added_to_hass()

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
        self.hass.components.mqtt.async_publish(
            dim_topic, self._dim, qos=0, retain=False
        )
        self.hass.components.mqtt.async_publish(
            backlight_topic, self._backlight, qos=0, retain=False
        )

        @callback
        async def idle_message_received(msg):
            """Process MQTT message from plate."""
            message = HASP_IDLE_SCHEMA(msg.payload)

            if message == HASP_IDLE_OFF:
                self._dim = self._awake_brightness
                self._backlight = 1
            elif message == HASP_IDLE_SHORT:
                self._dim = self._idle_brightness
                self._backlight = 1
            elif message == HASP_IDLE_LONG:
                self._dim = self._awake_brightness
                self._backlight = 0

            _LOGGER.debug(
                "Idle state is %s - Dimming %s to %s; Backlight %s to %s",
                msg.payload,
                dim_topic,
                self._dim,
                backlight_topic,
                self._backlight,
            )
            self.hass.components.mqtt.async_publish(
                backlight_topic, self._backlight, qos=0, retain=False
            )
            self.hass.components.mqtt.async_publish(
                dim_topic, self._dim, qos=0, retain=False
            )
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
            await self.hass.components.mqtt.async_subscribe(
                state_topic, page_message_received
            )


class HASPObject:
    """Representation of an HASP-LVGL."""

    def __init__(self, hass, plate_obj, config):
        """Initialize a object."""

        self.hass = hass
        self.obj_id = config[CONF_OBJID]
        self.command_topic = f"{plate_obj.topic}/command/{self.obj_id}."
        self.state_topic = f"{plate_obj.topic}/state/{self.obj_id}"
        self.properties = {}

        self.track_entity_id = config.get(CONF_TRACK)
        self.event_services = config.get(CONF_EVENT)

    @property
    def id(self):
        """Identification of the object pXbN."""
        return self.obj_id

    async def async_added_to_hass(self):
        """Run when entity about to be added."""

        if self.track_entity_id:
            await self.async_listen_state_changes("val")  # TODO support more then "val"

        if self.event_services:
            _LOGGER.debug("Setup event_services for %s", self.obj_id)
            await self.async_listen_hasp_events()

    def update_object_state(self, _property, entity_id, value):
        """Update back the Object in the plate."""

        domain = split_entity_id(entity_id)[0]
        # cast state values off/on to 0/1
        if domain in ["switch", "light", "input_boolean"] and value in TOGGLE:
            value = TOGGLE.index(value)
        # cast alarm_panel values to 0/1
        if domain == "alarm_panel" and value in ALARM:
            value = int(ALARM.index(value) > 0)

        self.hass.components.mqtt.async_publish(self.command_topic + _property, value)

    async def async_listen_state_changes(self, _property):
        """Listen to state changes."""

        self.properties[self.track_entity_id] = _property

        _LOGGER.debug(
            "Track Entity: %s -> %s",
            self.track_entity_id,
            self.command_topic + _property,
        )

        @callback
        def _update_hasp_obj(event):
            entity_id = event.data.get("entity_id")
            value = event.data.get("new_state").state

            _property = self.properties[entity_id]
            self.update_object_state(_property, entity_id, value)

        async_track_state_change_event(
            self.hass, self.track_entity_id, _update_hasp_obj
        )
        current_state = self.hass.states.get(self.track_entity_id)
        if current_state:
            value = current_state.state

            self.update_object_state(_property, self.track_entity_id, value)

    async def async_listen_hasp_events(self):
        """Listen to messages on MQTT for HASP events."""

        @callback
        async def message_received(msg):
            """Process object state MQTT message."""
            try:
                message = HASP_EVENT_SCHEMA(json.loads(msg.payload))

                for event in self.event_services:
                    if event in message[HASP_EVENT]:
                        _LOGGER.debug(
                            "Service call for %s triggered by %s on %s",
                            event,
                            msg.payload,
                            msg.topic,
                        )
                        await async_call_from_config(
                            self.hass, self.event_services[event], validate_config=True
                        )
            except vol.error.Invalid:
                _LOGGER.warning(
                    "Could not handle event %s on %s", msg.payload, msg.topic
                )

        _LOGGER.debug("Subscribe for %s events on %s", self.obj_id, self.state_topic)
        await self.hass.components.mqtt.async_subscribe(
            self.state_topic, message_received
        )
