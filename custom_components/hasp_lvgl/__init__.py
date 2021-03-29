"""HASP components module."""
import json
import logging
import os
import re

from homeassistant.components.light import DOMAIN as LIGHT_DOMAIN
from homeassistant.components import mqtt
from homeassistant.const import STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.core import callback
from homeassistant.helpers import discovery
from homeassistant.exceptions import TemplateError
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity_component import EntityComponent
from homeassistant.helpers.event import TrackTemplate, async_track_template_result
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.helpers.service import async_call_from_config
import voluptuous as vol

from .const import (
    ATTR_PAGE,
    ATTR_PATH,
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
    DEFAULT_IDLE_BRIGHNESS,
    DOMAIN,
    HASP_EVENT,
    HASP_EVENT_DOWN,
    HASP_EVENTS,
    HASP_HOME_PAGE,
    HASP_NUM_PAGES,
    HASP_MAX_PAGES,
    HASP_VAL,
    SERVICE_LOAD_PAGE,
    SERVICE_PAGE_CHANGE,
    SERVICE_PAGE_NEXT,
    SERVICE_PAGE_PREV,
    SERVICE_WAKEUP,
    SERVICE_CLEAR_PAGE,
)

from .common import HASPEntity

_LOGGER = logging.getLogger(__name__)


def hasp_object(value):
    """Validade HASP-LVGL object format."""
    if re.match("p[0-9]+b[0-9]+", value):
        return value
    raise vol.Invalid("Not an HASP-LVGL object p#b#")


# Configuration YAML schemas
EVENT_SCHEMA = cv.schema_with_slug_keys(cv.SERVICE_SCHEMA)

PROPERTY_SCHEMA = cv.schema_with_slug_keys(cv.template)

OBJECT_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_OBJID): hasp_object,
        vol.Optional(CONF_TRACK, default=None): vol.Any(cv.entity_id, None),
        vol.Optional(CONF_PROPERTIES, default={}): PROPERTY_SCHEMA,
        vol.Optional(CONF_EVENT, default={}): EVENT_SCHEMA,
    }
)

PAGES_SCHEMA = vol.Schema(
    {
        vol.Optional(CONF_PAGES_PREV): hasp_object,
        vol.Optional(CONF_PAGES_HOME): hasp_object,
        vol.Required(CONF_PAGES_NEXT): hasp_object,
    }
)

PLATE_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_OBJECTS): vol.All(cv.ensure_list, [OBJECT_SCHEMA]),
        vol.Required(CONF_PAGES): PAGES_SCHEMA,
        vol.Required(CONF_TOPIC): mqtt.valid_subscribe_topic,
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

HASP_STATUSUPDATE_SCHEMA = vol.Schema(
    {
        vol.Required("node"): cv.string,
        vol.Required("version"): cv.string,
        vol.Required("uptime"): int,
        vol.Required("canUpdate"): cv.boolean,
    },
    extra=vol.ALLOW_EXTRA,
)


async def async_setup(hass, config):
    """Set up the MQTT async example component."""
    component = EntityComponent(_LOGGER, DOMAIN, hass)

    for plate in config[DOMAIN]:
        plate_entity = SwitchPlate(hass, plate, config[DOMAIN][plate])

        await component.async_add_entities([plate_entity])

        component.async_register_entity_service(SERVICE_WAKEUP, {}, "async_wakeup")
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
        component.async_register_entity_service(
            SERVICE_CLEAR_PAGE, {vol.Optional(ATTR_PAGE): int}, "async_clearpage"
        )
        hass.async_create_task(
            discovery.async_load_platform(
                hass, LIGHT_DOMAIN, DOMAIN, (plate, config[DOMAIN][plate]), config
            )
        )

    return True


class SwitchPlate(HASPEntity, RestoreEntity):
    """Representation of an HASP-LVGL Plate."""

    def __init__(self, hass, plate, config):
        """Initialize a plate."""
        super().__init__()
        self._plate = plate
        self._topic = config[CONF_TOPIC]
        self._home_btn = config[CONF_PAGES].get(CONF_PAGES_HOME)
        self._prev_btn = config[CONF_PAGES].get(CONF_PAGES_PREV)
        self._next_btn = config[CONF_PAGES].get(CONF_PAGES_NEXT)
        self._pages_jsonl = config.get(CONF_PAGES_PATH)

        # Setup remaining objects
        self._objects = []
        for obj in config[CONF_OBJECTS]:
            new_obj = HASPObject(hass, self._topic, obj)

            self.add_object(new_obj)

        self._statusupdate = {HASP_NUM_PAGES: HASP_MAX_PAGES}
        self._available = False
        self._page = 1

    def add_object(self, obj):
        """Track objects in plate."""
        self._objects.append(obj)

    async def async_added_to_hass(self):
        """Run when entity about to be added."""
        await super().async_added_to_hass()

        if self._pages_jsonl:
            await self.async_load_page(self._pages_jsonl)

        state = await self.async_get_last_state()
        if state and state.state not in [STATE_UNAVAILABLE, STATE_UNKNOWN, None]:
            self._page = int(state.state)

        await self.async_setup_pages()

        for obj in self._objects:
            await obj.async_added_to_hass()

        @callback
        async def statusupdate_message_received(msg):
            """Process statusupdate."""

            try:
                message = HASP_STATUSUPDATE_SCHEMA(json.loads(msg.payload))

                self._available = True
                self._statusupdate = message
                self._page = message[ATTR_PAGE]
                self.async_write_ha_state()

            except vol.error.Invalid as err:
                _LOGGER.error(err)

        await self.hass.components.mqtt.async_subscribe(
            self._topic + "/state/statusupdate", statusupdate_message_received
        )
        self.hass.components.mqtt.async_publish(
            self._topic + "/command", "statusupdate", qos=0, retain=False
        )

    @property
    def unique_id(self):
        """Return the plate identifier."""
        return self._plate

    @property
    def icon(self):
        """Return the icon to be used for this entity."""
        return "mdi:light-switch"

    @property
    def state(self):
        """Return the state of the component."""
        return self._page

    @property
    def available(self):
        """Return if entity is available."""
        return self._available

    @property
    def state_attributes(self):
        """Return the state attributes."""
        attributes = {}

        if self._statusupdate:
            attributes = {**attributes, **self._statusupdate}

        return attributes

    async def async_wakeup(self):
        """Wake up the display."""
        cmd_topic = f"{self._topic}/command"
        _LOGGER.debug("Wakeup")
        self.hass.components.mqtt.async_publish(
            cmd_topic, "wakeup", qos=0, retain=False
        )

    async def async_change_page_next(self):
        """Change page to next one."""
        await self.async_change_page(self._page + 1)

    async def async_change_page_prev(self):
        """Change page to previous one."""
        await self.async_change_page(self._page - 1)

    async def async_clearpage(self, page="all"):
        """Clear page."""
        cmd_topic = f"{self._topic}/command"

        self.hass.components.mqtt.async_publish(
            cmd_topic, f"clearpage {page}", qos=0, retain=False
        )

        if page == "all":
            self.hass.components.mqtt.async_publish(
                cmd_topic, "page 1", qos=0, retain=False
            )

    async def async_change_page(self, page):
        """Change page to number."""
        cmd_topic = f"{self._topic}/command/page"

        if self._statusupdate:
            num_pages = self._statusupdate[HASP_NUM_PAGES]

            if page <= 0 or page > num_pages:
                _LOGGER.error(
                    "Can't change to %s, available pages are 1 to %s", page, num_pages
                )
                return

        self._page = page

        _LOGGER.debug("Change page %s", self._page)
        self.hass.components.mqtt.async_publish(
            cmd_topic, self._page, qos=0, retain=False
        )
        self.async_write_ha_state()

    async def async_setup_pages(self):
        """Listen to messages on MQTT for HASP Page changes."""

        async def page_message_received(msg):
            """Process MQTT message from plate."""
            _LOGGER.debug("Page button received: %s ", msg.topic)

            try:
                cmd = HASP_EVENT_SCHEMA(json.loads(msg.payload))

                if cmd[HASP_EVENT] != HASP_EVENT_DOWN:
                    return

                if msg.topic.endswith(self._prev_btn):
                    await self.async_change_page_prev()
                if msg.topic.endswith(self._home_btn):
                    await self.async_change_page(HASP_HOME_PAGE)
                if msg.topic.endswith(self._next_btn):
                    await self.async_change_page_next()

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

    async def refresh(self):
        """Refresh objects in the SwitchPlate."""

        if self._pages_jsonl:
            await self.async_load_page(self._pages_jsonl)

        for obj in self._objects:
            await obj.refresh()

        await self.async_change_page(self._page)

    async def async_load_page(self, path):
        """Clear current pages and load new ones."""
        cmd_topic = f"{self._topic}/command"
        _LOGGER.info("Load page %s to %s", path, cmd_topic)

        if not self.hass.config.is_allowed_path(path):
            _LOGGER.error("'%s' is not an allowed directory", path)
            return

        try:
            with open(path) as pages_jsonl:
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
            _LOGGER.debug("Setup event_services for '%s'", self.obj_id)
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
                            "Service call for '%s' triggered by '%s' on '%s'",
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
                    "Could not handle event '%s' on '%s'", msg.payload, msg.topic
                )

        _LOGGER.debug(
            "Subscribe for '%s' events on '%s'", self.obj_id, self.state_topic
        )
        await self.hass.components.mqtt.async_subscribe(
            self.state_topic, message_received
        )
