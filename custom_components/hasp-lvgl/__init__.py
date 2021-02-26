"""HASP components module."""
import logging
import json
from homeassistant.core import callback, DOMAIN as HA_DOMAIN
from homeassistant.components import mqtt
from homeassistant.const import SERVICE_TURN_OFF, SERVICE_TURN_ON, ATTR_ENTITY_ID
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.event import async_track_state_change_event

from .consts import (
    DOMAIN,
    TOGGLE,
    CONF_OBJID,
    CONF_ENTITY,
    CONF_TOPIC,
    CONF_PAGE_ENTITY,
    CONF_OBJECTS,
    DEFAULT_TOPIC,
)

import voluptuous as vol

_LOGGER = logging.getLogger(__name__)

OBJECT_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_OBJID): cv.string,
        vol.Optional(CONF_ENTITY): cv.entity_id,
    }
)

PLATE_SCHEMA = vol.Schema(
    {
        vol.Optional(CONF_PAGE_ENTITY): cv.entity_id,
        vol.Optional(CONF_TOPIC): mqtt.valid_subscribe_topic,
        vol.Required(CONF_OBJECTS): vol.All(cv.ensure_list, [OBJECT_SCHEMA]),
    },
    extra=vol.ALLOW_EXTRA,
)

CONFIG_SCHEMA = vol.Schema(
    {DOMAIN: vol.Schema({cv.slug: PLATE_SCHEMA})}, extra=vol.ALLOW_EXTRA
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

        schema = vol.Schema(
            {vol.Required("val"): vol.All(int, vol.Range(min=0, max=1))}
        )
        cmd = schema(json.loads(msg.payload))

        service = SERVICE_TURN_OFF
        if cmd["val"] == 1:
            service = SERVICE_TURN_ON

        await hass.services.async_call(
            HA_DOMAIN, service, {ATTR_ENTITY_ID: entity_id}
        )

    await hass.components.mqtt.async_subscribe(
        state_topic, message_received
    )


async def async_setup(hass, config):
    """Set up the MQTT async example component."""

    hass.data[DOMAIN] = {}

    for plate in config[DOMAIN]:
        hass.data[DOMAIN][plate] = {
            CONF_TOPIC: config[DOMAIN][plate][CONF_TOPIC]
        }
        for obj in config[DOMAIN][plate][CONF_OBJECTS]:
            entity_id = obj[CONF_ENTITY]
            domain = entity_id.split(".", 1)[0]
            objid = obj[CONF_OBJID]

            await async_listen_state_changes(hass, entity_id, plate, objid)

            if domain in ["switch", "light", "media_player"]:
                await async_listen_hasp_changes(hass, objid, plate, entity_id)

    return True