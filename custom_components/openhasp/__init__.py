"""HASP components module."""
import json
import logging
import os
import re

from homeassistant.components import mqtt
from homeassistant.components.light import DOMAIN as LIGHT_DOMAIN
from homeassistant.components.switch import DOMAIN as SWITCH_DOMAIN
from homeassistant.const import STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.core import callback
from homeassistant.exceptions import TemplateError
from homeassistant.helpers import discovery
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity_component import EntityComponent
from homeassistant.helpers.event import TrackTemplate, async_track_template_result
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.helpers.service import async_call_from_config
import voluptuous as vol

from .common import HASP_IDLE_SCHEMA
from .const import (
    ATTR_IDLE,
    ATTR_PAGE,
    ATTR_PATH,
    CONF_EVENT,
    CONF_GPIO,
    CONF_IDLE_BRIGHTNESS,
    CONF_LEDS,
    CONF_OBJECTS,
    CONF_OBJID,
    CONF_PAGES_PATH,
    CONF_PLATE,
    CONF_PROPERTIES,
    CONF_PWMS,
    CONF_RELAYS,
    CONF_TOPIC,
    CONF_TRACK,
    DEFAULT_IDLE_BRIGHNESS,
    DOMAIN,
    EVENT_HASP_PLATE_OFFLINE,
    EVENT_HASP_PLATE_ONLINE,
    HASP_EVENT,
    HASP_EVENT_DOWN,
    HASP_EVENT_RELEASE,
    HASP_EVENT_UP,
    HASP_EVENTS,
    HASP_LWT,
    HASP_MAX_PAGES,
    HASP_NUM_PAGES,
    HASP_ONLINE,
    HASP_VAL,
    SERVICE_CLEAR_PAGE,
    SERVICE_LOAD_PAGE,
    SERVICE_PAGE_CHANGE,
    SERVICE_PAGE_NEXT,
    SERVICE_PAGE_PREV,
    SERVICE_WAKEUP,
    MAJOR,
    MINOR,
)

_LOGGER = logging.getLogger(__name__)


def hasp_object(value):
    """Validade HASP-LVGL object format."""
    if re.match("p[0-9]+b[0-9]+", value):
        return value
    raise vol.Invalid("Not an HASP-LVGL object p#b#")


# Configuration YAML schemas
EVENT_SCHEMA = cv.schema_with_slug_keys([cv.SERVICE_SCHEMA])

PROPERTY_SCHEMA = cv.schema_with_slug_keys(cv.template)

OBJECT_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_OBJID): hasp_object,
        vol.Optional(CONF_TRACK, default=None): vol.Any(cv.entity_id, None),
        vol.Optional(CONF_PROPERTIES, default={}): PROPERTY_SCHEMA,
        vol.Optional(CONF_EVENT, default={}): EVENT_SCHEMA,
    }
)

GPIO_SCHEMA = vol.Schema(
    {
        vol.Optional(CONF_RELAYS): vol.All(cv.ensure_list, [cv.positive_int]),
        vol.Optional(CONF_LEDS): vol.All(cv.ensure_list, [cv.positive_int]),
        vol.Optional(CONF_PWMS): vol.All(cv.ensure_list, [cv.positive_int]),
    }
)

PLATE_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_OBJECTS): vol.All(cv.ensure_list, [OBJECT_SCHEMA]),
        vol.Required(CONF_TOPIC): mqtt.valid_subscribe_topic,
        vol.Optional(CONF_GPIO): GPIO_SCHEMA,
        vol.Optional(CONF_IDLE_BRIGHTNESS, default=DEFAULT_IDLE_BRIGHNESS): vol.All(
            int, vol.Range(min=0, max=255)
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

HASP_LWT_SCHEMA = vol.Schema(vol.Any(*HASP_LWT))

HASP_PAGE_SCHEMA = vol.Schema(vol.All(vol.Coerce(int), vol.Range(min=0, max=12)))


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

        discovery_info = {
            CONF_PLATE: plate,
            CONF_TOPIC: config[DOMAIN][plate][CONF_TOPIC],
            CONF_IDLE_BRIGHTNESS: config[DOMAIN][plate][CONF_IDLE_BRIGHTNESS],
        }

        hass.async_create_task(
            discovery.async_load_platform(
                hass,
                LIGHT_DOMAIN,
                DOMAIN,
                discovery_info,
                config,
            )
        )

        if (
            CONF_GPIO in config[DOMAIN][plate]
            and CONF_RELAYS in config[DOMAIN][plate][CONF_GPIO]
        ):
            discovery_info[CONF_RELAYS] = config[DOMAIN][plate][CONF_GPIO][CONF_RELAYS]

            hass.async_create_task(
                discovery.async_load_platform(
                    hass,
                    SWITCH_DOMAIN,
                    DOMAIN,
                    discovery_info,
                    config,
                )
            )

    return True


# pylint: disable=R0902
class SwitchPlate(RestoreEntity):
    """Representation of an HASP-LVGL Plate."""

    def __init__(self, hass, plate, config):
        """Initialize a plate."""
        super().__init__()
        self._plate = plate
        self._topic = config[CONF_TOPIC]
        self._pages_jsonl = config.get(CONF_PAGES_PATH)

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

        state = await self.async_get_last_state()
        if state and state.state not in [STATE_UNAVAILABLE, STATE_UNKNOWN, None]:
            self._page = int(state.state)

        for obj in self._objects:
            await obj.async_added_to_hass()

        @callback
        async def page_update_received(msg):
            """Process page state."""
            try:
                self._page = HASP_PAGE_SCHEMA(msg.payload)
                _LOGGER.debug("Page changed to %s", self._page)
                self.async_write_ha_state()
            except vol.error.Invalid as err:
                _LOGGER.error("%s in %s", err, msg.payload)

        await self.hass.components.mqtt.async_subscribe(
            self._topic + "/state/page", page_update_received
        )

        @callback
        async def statusupdate_message_received(msg):
            """Process statusupdate."""

            try:
                message = HASP_STATUSUPDATE_SCHEMA(json.loads(msg.payload))

                major, minor, _ = message["version"].split(".")
                if (major, minor) != (MAJOR, MINOR):
                    self.hass.components.persistent_notification.create(
                        f"You require firmware version {MAJOR}.{MINOR}.x \
                            in plate {self._plate} for this component to work properly.\
                            <br>Some features will simply not work!",
                        title="openHASP Firmware mismatch",
                        notification_id="openhasp_firmware_notification",
                    )
                    _LOGGER.error(
                        "%s firmware mismatch %s <> %s",
                        self._plate,
                        (major, minor),
                        (MAJOR, MINOR),
                    )
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

        @callback
        async def idle_message_received(msg):
            """Process idle message."""
            try:
                self._statusupdate[ATTR_IDLE] = HASP_IDLE_SCHEMA(msg.payload)
                self.async_write_ha_state()
            except vol.error.Invalid as err:
                _LOGGER.error(err)

        await self.hass.components.mqtt.async_subscribe(
            self._topic + "/state/idle", idle_message_received
        )

        @callback
        async def lwt_message_received(msg):
            """Process LWT."""
            _LOGGER.debug("Received LWT = %s", msg.payload)
            try:
                message = HASP_LWT_SCHEMA(msg.payload)

                if message == HASP_ONLINE:
                    self._available = True
                    self.hass.bus.async_fire(
                        EVENT_HASP_PLATE_ONLINE, {CONF_PLATE: self._plate}
                    )
                    if self._pages_jsonl:
                        await self.async_load_page(self._pages_jsonl)
                    else:
                        await self.refresh()
                else:
                    self._available = False
                    self.hass.bus.async_fire(
                        EVENT_HASP_PLATE_OFFLINE, {CONF_PLATE: self._plate}
                    )

                self.async_write_ha_state()

            except vol.error.Invalid as err:
                _LOGGER.error(err)

        await self.hass.components.mqtt.async_subscribe(
            f"{self._topic}/LWT", lwt_message_received
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

        if ATTR_PAGE in attributes:
            del attributes[
                ATTR_PAGE
            ]  # Page is tracked in the state, don't confuse users

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
        cmd_topic = f"{self._topic}/command/page"

        self.hass.components.mqtt.async_publish(
            cmd_topic, "page next", qos=0, retain=False
        )

    async def async_change_page_prev(self):
        """Change page to previous one."""
        cmd_topic = f"{self._topic}/command/page"

        self.hass.components.mqtt.async_publish(
            cmd_topic, "page prev", qos=0, retain=False
        )

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

    async def refresh(self):
        """Refresh objects in the SwitchPlate."""

        _LOGGER.warning("Refreshing %s", self._plate)
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
            await self.refresh()

        except (IndexError, FileNotFoundError, IsADirectoryError, UnboundLocalError):
            _LOGGER.warning(
                "File or data not present at the moment: %s",
                os.path.basename(path),
            )
            return


# pylint: disable=R0902
class HASPObject:
    """Representation of an HASP-LVGL object."""

    def __init__(self, hass, plate_topic, config):
        """Initialize an object."""

        self.hass = hass
        self.obj_id = config[CONF_OBJID]
        self.command_topic = f"{plate_topic}/command/{self.obj_id}."
        self.state_topic = f"{plate_topic}/state/{self.obj_id}"
        self.cached_properties = {}

        self.properties = config.get(CONF_PROPERTIES)
        self.event_services = config.get(CONF_EVENT)
        self._freeze_properties = []

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

            if isinstance(result, TemplateError) or result is None:
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

            self.cached_properties[_property] = result
            if _property in self._freeze_properties:
                # Skip update to plate to avoid feedback loops
                return

            _LOGGER.debug(
                "%s.%s - %s changed, updating with: %s",
                self.obj_id,
                _property,
                template,
                result,
            )

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
        """Refresh based on cached values."""
        for _property, result in self.cached_properties.items():
            _LOGGER.debug("Refresh object %s.%s = %s", self.obj_id, _property, result)
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

                if message[HASP_EVENT] == HASP_EVENT_DOWN:
                    # store properties that shouldn't be updated while button pressed
                    self._freeze_properties = message.keys()
                elif message[HASP_EVENT] in [HASP_EVENT_UP, HASP_EVENT_RELEASE]:
                    self._freeze_properties = []

                for event in self.event_services:
                    if event in message[HASP_EVENT]:
                        _LOGGER.debug(
                            "Service call for '%s' triggered by '%s' on '%s' with variables %s",
                            event,
                            msg.payload,
                            msg.topic,
                            message,
                        )
                        for service in self.event_services[event]:
                            await async_call_from_config(
                                self.hass,
                                service,
                                validate_config=False,
                                variables=message,
                            )
            except vol.error.Invalid:
                _LOGGER.warning(
                    "Could not handle openHASP event: '%s' on '%s'",
                    msg.payload,
                    msg.topic,
                )
            except json.decoder.JSONDecodeError as err:
                _LOGGER.error(
                    "Error decoding received JSON message: %s on %s", err.doc, msg.topic
                )

        _LOGGER.debug("Subscribe to '%s' events on '%s'", self.obj_id, self.state_topic)
        await self.hass.components.mqtt.async_subscribe(
            self.state_topic, message_received
        )
