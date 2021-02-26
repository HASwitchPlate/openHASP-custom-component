"""HASP components module."""
import logging
import json
from homeassistant.core import callback, DOMAIN as HA_DOMAIN
from homeassistant.components import mqtt
from homeassistant.const import SERVICE_TURN_OFF, SERVICE_TURN_ON, ATTR_ENTITY_ID
from homeassistant.components.number.const import SERVICE_SET_VALUE, ATTR_VALUE, DOMAIN as NUMBER_DOMAIN
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.event import async_track_state_change_event

from .const import (
    DOMAIN,
    TOGGLE,
    CONF_OBJID,
    CONF_ENTITY,
    CONF_TOPIC,
    CONF_PAGES,
    CONF_PAGE_ENTITY,
    CONF_PAGES_PREV,
    CONF_PAGES_HOME,
    CONF_PAGES_NEXT,    
    CONF_OBJECTS,
    DEFAULT_TOPIC,
    HASP_VAL,
    HASP_EVENT,
    HASP_HOME_PAGE
)

import voluptuous as vol

_LOGGER = logging.getLogger(__name__)


# Configuration YAML schemas
OBJECT_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_OBJID): cv.string,
        vol.Optional(CONF_ENTITY): cv.entity_id,
    }
)

PAGES_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_ENTITY): cv.entity_id,
        vol.Optional(CONF_PAGES_PREV): cv.string,
        vol.Optional(CONF_PAGES_HOME): cv.string,
        vol.Optional(CONF_PAGES_NEXT): cv.string,
    }
)

PLATE_SCHEMA = vol.Schema(
    {
        vol.Optional(CONF_PAGES): PAGES_SCHEMA,
        vol.Optional(CONF_TOPIC): mqtt.valid_subscribe_topic,
        vol.Required(CONF_OBJECTS): vol.All(cv.ensure_list, [OBJECT_SCHEMA]),
    },
    extra=vol.ALLOW_EXTRA,
)

CONFIG_SCHEMA = vol.Schema(
    {DOMAIN: vol.Schema({cv.slug: PLATE_SCHEMA})}, extra=vol.ALLOW_EXTRA
)

# JSON Messages from HASP schemas
HASP_VAL_SCHEMA = vol.Schema(
    {vol.Required(HASP_VAL): vol.All(int, vol.Range(min=0, max=1))}
)
HASP_EVENT_SCHEMA = vol.Schema(
    {vol.Required(HASP_EVENT): vol.Any('DOWN', 'UP', 'SHORT', 'LONG')}
)

async def async_listen_state_changes(hass, entity_id, plate, obj):
    """ Listen to state changes """
    command_topic = (
        f"{hass.data[DOMAIN][plate][CONF_TOPIC]}/command/{obj}.val"
    )
    hass.data[DOMAIN][plate][entity_id] = command_topic
    _LOGGER.debug("Track Entity: %s -> %s", entity_id, command_topic)

    @callback
    def _update_hasp_obj(event, plate):
        entity_id = event.data.get("entity_id")
        value = event.data.get("new_state").state

        # cast binary_sensor to 0/1
        if value in TOGGLE:
            value = TOGGLE.index(value)

        topic = hass.data[DOMAIN][plate].get(entity_id)

        _LOGGER.debug("_update_hasp_obj(%s) = %s", topic, value)
        hass.components.mqtt.async_publish(topic, value)

    async_track_state_change_event(hass, entity_id, lambda e: _update_hasp_obj(e, plate))

async def async_listen_hasp_changes(hass, obj, plate, entity_id):
    """Listen to messages on MQTT for HASP changes."""
    state_topic = (
        f"{hass.data[DOMAIN][plate][CONF_TOPIC]}/state/{obj}"
    )

    _LOGGER.debug("Track MQTT: %s -> %s", state_topic, entity_id)

    hass.data[DOMAIN][plate][state_topic] = entity_id

    async def message_received(msg):
        """Process MQTT message from plate."""
        entity_id = hass.data[DOMAIN][plate][msg.topic]
        _LOGGER.debug("%s - %s - %s", msg.topic, entity_id, msg.payload)

        # Parse received JSON
        cmd = HASP_VAL_SCHEMA(json.loads(msg.payload))

        service = SERVICE_TURN_OFF
        if cmd[HASP_VAL] == 1:
            service = SERVICE_TURN_ON

        await hass.services.async_call(
            HA_DOMAIN, service, {ATTR_ENTITY_ID: entity_id}
        )

    await hass.components.mqtt.async_subscribe(
        state_topic, message_received
    )

async def async_setup_pages(hass, plate, obj_prev, obj_home, obj_next):
    """Listen to messages on MQTT for HASP Page changes."""

    hass.data[DOMAIN][plate][CONF_PAGES_PREV] = obj_prev
    hass.data[DOMAIN][plate][CONF_PAGES_HOME] = obj_home
    hass.data[DOMAIN][plate][CONF_PAGES_NEXT] = obj_next

    async def message_received(msg):
        """Process MQTT message from plate."""
        _LOGGER.debug("Track page button: %s ", msg.topic)
    
        # Parse received JSON
        cmd = HASP_EVENT_SCHEMA(json.loads(msg.payload))
        if cmd[HASP_EVENT] != 'DOWN':
            return

        page_state = hass.states.get(hass.data[DOMAIN][plate][CONF_PAGE_ENTITY])
        new_value = int(page_state.state)

        if msg.topic.endswith(hass.data[DOMAIN][plate][CONF_PAGES_PREV]):
            new_value -= 1
        if msg.topic.endswith(hass.data[DOMAIN][plate][CONF_PAGES_HOME]):
            new_value = HASP_HOME_PAGE
        if msg.topic.endswith(hass.data[DOMAIN][plate][CONF_PAGES_NEXT]):
            new_value += 1

        await hass.services.async_call(
            NUMBER_DOMAIN, SERVICE_SET_VALUE, {
                ATTR_ENTITY_ID: hass.data[DOMAIN][plate][CONF_PAGE_ENTITY],
                ATTR_VALUE: new_value
                }
        )

    for obj in [obj_prev, obj_home, obj_next]:
        if obj is None:
            continue

        state_topic = (
            f"{hass.data[DOMAIN][plate][CONF_TOPIC]}/state/{obj}"
        )
        _LOGGER.debug("Track page button: %s -> %s", obj, state_topic)
        await hass.components.mqtt.async_subscribe(
            state_topic, message_received
        )


async def async_setup(hass, config):
    """Set up the MQTT async example component."""

    hass.data[DOMAIN] = {}

    for plate in config[DOMAIN]:
        hass.data[DOMAIN][plate] = {
            CONF_TOPIC: config[DOMAIN][plate][CONF_TOPIC],
            CONF_PAGE_ENTITY: config[DOMAIN][plate][CONF_PAGES][CONF_ENTITY],
        }
        await async_setup_pages(
            hass, plate, 
            config[DOMAIN][plate][CONF_PAGES][CONF_PAGES_PREV],
            config[DOMAIN][plate][CONF_PAGES][CONF_PAGES_HOME],
            config[DOMAIN][plate][CONF_PAGES][CONF_PAGES_NEXT],
        )
        for obj in config[DOMAIN][plate][CONF_OBJECTS]:
            entity_id = obj[CONF_ENTITY]
            domain = entity_id.split(".", 1)[0]
            objid = obj[CONF_OBJID]

            await async_listen_state_changes(hass, entity_id, plate, objid)

            if domain in ["switch", "light", "media_player"]:
                await async_listen_hasp_changes(hass, objid, plate, entity_id)

    return True