"""HASP components module."""
import json
import logging
import os

from homeassistant.components import mqtt
from homeassistant.core import callback
from homeassistant.exceptions import TemplateError
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity_component import EntityComponent
from homeassistant.helpers.event import TrackTemplate, async_track_template_result
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.helpers.service import async_call_from_config
import voluptuous as vol

from .const import (
    ATTR_CURRENT_DIM,
    ATTR_PAGE,
    ATTR_PATH,
    CONF_AWAKE_BRIGHTNESS,
    CONF_EVENT,
    CONF_IDLE_BRIGHTNESS,
    CONF_OBJECTS,
    CONF_OBJID,
    CONF_PAGES,
    CONF_PAGES_HOME,
    CONF_PAGES_NEXT,
    CONF_PAGES_PATH,
    CONF_PAGES_PREV,
    CONF_PROPERTIES,
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
    HASP_LWT,
    HASP_ONLINE,
    HASP_VAL,
    SERVICE_LOAD_PAGE,
    SERVICE_PAGE_CHANGE,
    SERVICE_PAGE_NEXT,
    SERVICE_PAGE_PREV,
)

_LOGGER = logging.getLogger(__name__)


# Configuration YAML schemas
EVENT_SCHEMA = cv.schema_with_slug_keys(cv.SERVICE_SCHEMA)

PROPERTY_SCHEMA = cv.schema_with_slug_keys(cv.template)

OBJECT_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_OBJID): cv.string,  # TODO validade string is an object p#b#
        vol.Optional(CONF_TRACK, default=None): vol.Any(cv.entity_id, None),
        vol.Optional(CONF_PROPERTIES, default={}): PROPERTY_SCHEMA,
        vol.Optional(CONF_EVENT, default={}): EVENT_SCHEMA,
    }
)

PAGES_SCHEMA = vol.Schema(
    {
        vol.Optional(
            CONF_PAGES_PREV
        ): cv.string,  # TODO validade string is an object p#b#
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
        vol.Optional(CONF_PAGES_PATH): cv.isfile,
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

HASP_LWT_SCHEMA = vol.Schema(vol.Any(*HASP_LWT))


async def async_setup(hass, config):
    """Set up the MQTT async example component."""
    component = EntityComponent(_LOGGER, DOMAIN, hass)

    for plate in config[DOMAIN]:
        plate = SwitchPlate(hass, plate, config[DOMAIN][plate])

        await component.async_add_entities([plate])

        component.async_register_entity_service(
            SERVICE_PAGE_NEXT, {}, "async_change_page_next"
        )
        component.async_register_entity_service(
            SERVICE_PAGE_PREV, {}, "async_change_page_prev"
        )
        component.async_register_entity_service(
            SERVICE_PAGE_CHANGE, {vol.Required(ATTR_PAGE): int}, "async_change_page"
        )

        component.async_register_entity_service(
            SERVICE_LOAD_PAGE, {vol.Required(ATTR_PATH): cv.isfile}, "async_load_page"
        )

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
        self._pages_jsonl = config.get(CONF_PAGES_PATH)

        # Setup remaining objects
        self._objects = []
        for obj in config[CONF_OBJECTS]:
            new_obj = HASPObject(hass, self._topic, obj)

            self.add_object(new_obj)

        self._page = 1
        self._dim = 0
        self._backlight = 1

    def add_object(self, obj):
        """Track objects in plate."""
        self._objects.append(obj)

    async def refresh(self):
        """Refresh objects in the SwitchPlate."""

        if self._pages_jsonl:
            await self.async_load_page(self._pages_jsonl)

        for obj in self._objects:
            await obj.refresh()

    async def async_added_to_hass(self):
        """Run when entity about to be added."""
        await super().async_added_to_hass()

        if self._pages_jsonl:
            await self.async_load_page(self._pages_jsonl)

        state = await self.async_get_last_state()
        if state:
            self._page = int(state.state)
            self._dim = int(state.attributes.get(ATTR_CURRENT_DIM))
            _LOGGER.debug("Restore DIM to %s", self._dim)

        await self.async_listen_idleness()
        await self.async_setup_pages()

        for obj in self._objects:
            await obj.async_added_to_hass()

        @callback
        async def lwt_message_received(msg):
            """Process LWT."""

            try:
                message = HASP_LWT_SCHEMA(msg.payload)

                if message == HASP_ONLINE:
                    await self.refresh()
            except vol.error.Invalid as err:
                _LOGGER.error(err)

        await self.hass.components.mqtt.async_subscribe(
            self._topic + "/LWT", lwt_message_received
        )

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
        return {
            ATTR_PAGE: self._page,
            ATTR_CURRENT_DIM: self._dim,
        }

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
                self._dim = self._idle_brightness
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

    async def async_change_page_next(self):
        """Change page to next one."""
        await self.async_change_page(self._page + 1)

    async def async_change_page_prev(self):
        """Change page to previous one."""

        await self.async_change_page(self._page - 1)

    async def async_change_page(self, page):
        """Change page to number."""
        cmd_topic = f"{self._topic}/command/page"

        if page <= 0:
            _LOGGER.error("Can't change to %s, first page is 1.", page)
            return

        self._page = page

        _LOGGER.debug("Change page %s to %s", cmd_topic, self._page)
        self.hass.components.mqtt.async_publish(
            cmd_topic, self._page, qos=0, retain=False
        )
        self.async_write_ha_state()

    async def async_setup_pages(self):
        """Listen to messages on MQTT for HASP Page changes."""

        async def page_message_received(msg):
            """Process MQTT message from plate."""
            _LOGGER.debug("Page button received: %s ", msg.topic)

            # Parse received JSON
            try:
                cmd = HASP_EVENT_SCHEMA(json.loads(msg.payload))

                if cmd[HASP_EVENT] != HASP_EVENT_DOWN:
                    return

                if msg.topic.endswith(self._prev_btn):
                    await self.async_change_page(self._page - 1)
                if msg.topic.endswith(self._home_btn):
                    await self.async_change_page(HASP_HOME_PAGE)
                if msg.topic.endswith(self._next_btn):
                    await self.async_change_page(self._page + 1)

            except vol.error.Invalid as err:
                _LOGGER.error(err)

        for obj in [self._prev_btn, self._home_btn, self._next_btn]:
            if obj is None:
                continue

            state_topic = f"{self._topic}/state/{obj}"
            _LOGGER.debug("Track page button: %s -> %s", obj, state_topic)
            await self.hass.components.mqtt.async_subscribe(
                state_topic, page_message_received
            )

    async def async_load_page(self, path):
        """Clear current pages and load new ones."""
        cmd_topic = f"{self._topic}/command"
        _LOGGER.info("Load page %s to %s", path, cmd_topic)

        if not self.hass.config.is_allowed_path(path):
            _LOGGER.error("'%s' is not an allowed directory", path)
            return

        try:
            with open(path) as pages_jsonl:
                # clear current pages
                for page in range(1, 12):
                    self.hass.components.mqtt.async_publish(
                        cmd_topic, f"clearpage {page}", qos=0, retain=False
                    )
                # load line by line
                for line in pages_jsonl:
                    if line:
                        self.hass.components.mqtt.async_publish(
                            f"{cmd_topic}/jsonl", line, qos=0, retain=False
                        )

        except (IndexError, FileNotFoundError, IsADirectoryError, UnboundLocalError):
            _LOGGER.warning(
                "File or data not present at the moment: %s",
                os.path.basename(path),
            )
            return


class HASPObject:
    """Representation of an HASP-LVGL."""

    def __init__(self, hass, plate_topic, config):
        """Initialize a object."""

        self.hass = hass
        self.obj_id = config[CONF_OBJID]
        self.command_topic = f"{plate_topic}/command/{self.obj_id}."
        self.state_topic = f"{plate_topic}/state/{self.obj_id}"
        self.cached_properties = {}

        self.properties = config.get(CONF_PROPERTIES)
        self.event_services = config.get(CONF_EVENT)

    async def async_added_to_hass(self):
        """Run when entity about to be added."""

        if self.event_services:
            _LOGGER.debug("Setup event_services for %s", self.obj_id)
            await self.async_listen_hasp_events()

        for _property, template in self.properties.items():
            await self.async_set_property(_property, template)

    async def async_set_property(self, _property, template):
        """Set HASP Object property to template value."""

        @callback
        def _async_template_result_changed(event, updates):
            track_template_result = updates.pop()
            template = track_template_result.template
            result = track_template_result.result

            if isinstance(result, TemplateError):
                entity = event and event.data.get("entity_id")
                _LOGGER.error(
                    "TemplateError('%s') "
                    "while processing template '%s' "
                    "in entity '%s'",
                    result,
                    template,
                    entity,
                )
                return

            _LOGGER.debug(
                "%s.%s - %s changed, updating with: %s",
                self.obj_id,
                _property,
                template,
                result,
            )

            self.cached_properties[_property] = result
            self.hass.components.mqtt.async_publish(
                self.command_topic + _property, result
            )

        property_template = async_track_template_result(
            self.hass,
            [TrackTemplate(template, None)],
            _async_template_result_changed,
        )
        property_template.async_refresh()

    async def refresh(self):
        """Force template eval."""
        for _property, result in self.cached_properties.items():
            _LOGGER.debug("Refresh %s.%s = %s", self.obj_id, _property, result)
            self.hass.components.mqtt.async_publish(
                self.command_topic + _property, result
            )

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
                            self.hass,
                            self.event_services[event],
                            validate_config=True,
                            variables=message,
                        )
            except vol.error.Invalid:
                _LOGGER.warning(
                    "Could not handle event %s on %s", msg.payload, msg.topic
                )

        _LOGGER.debug("Subscribe for %s events on %s", self.obj_id, self.state_topic)
        await self.hass.components.mqtt.async_subscribe(
            self.state_topic, message_received
        )
