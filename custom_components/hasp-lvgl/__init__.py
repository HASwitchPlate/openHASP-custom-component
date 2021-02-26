"""HASP components module."""
import logging
import json
from homeassistant.core import callback
from homeassistant.components import mqtt
from homeassistant.const import SERVICE_TURN_OFF, SERVICE_TURN_ON, ATTR_ENTITY_ID
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.event import async_track_state_change_event

import voluptuous as vol

_LOGGER = logging.getLogger(__name__)


DOMAIN = "hasp-lvgl"

CONF_OBJID = "obj"
CONF_ENTITY = "entity"
CONF_TOPIC = "topic"
CONF_OBJECTS = "objects"

DEFAULT_TOPIC = "hasp"

OBJECT_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_OBJID): cv.string,
        vol.Required(CONF_ENTITY): cv.entity_id,
    }
)

PLATE_SCHEMA = vol.Schema(
    {
        vol.Optional(CONF_TOPIC): mqtt.valid_subscribe_topic,
        vol.Required(CONF_OBJECTS): vol.All(cv.ensure_list, [OBJECT_SCHEMA]),
    },
    extra=vol.ALLOW_EXTRA,
)

CONFIG_SCHEMA = vol.Schema(
    {DOMAIN: vol.Schema({cv.slug: PLATE_SCHEMA})}, extra=vol.ALLOW_EXTRA
)


async def async_setup(hass, config):
    """Set up the MQTT async example component."""

    hass.data[DOMAIN] = {}

    for plate in config[DOMAIN]:
        hass.data[DOMAIN][plate] = {}
        for obj in config[DOMAIN][plate][CONF_OBJECTS]:
            entity_id = obj[CONF_ENTITY]
            domain = entity_id.split(".", 1)[0]

            # Listen to state changes
            command_topic = (
                f"{config[DOMAIN][plate][CONF_TOPIC]}/command/{obj[CONF_OBJID]}.val"
            )
            _LOGGER.debug("Track Entity: %s -> %s", entity_id, command_topic)

            hass.data[DOMAIN][plate][entity_id] = command_topic

            @callback
            def _update_hasp_obj(event):
                entity_id = event.data.get("entity_id")
                value = event.data.get("new_state").state

                if value == "on":
                    value = 1
                elif value == "off":
                    value = 0

                topic = hass.data[DOMAIN][plate].get(entity_id)

                _LOGGER.debug("_update_hasp_obj(%s) = %s", topic, value)
                hass.components.mqtt.async_publish(topic, value)

            async_track_state_change_event(hass, entity_id, _update_hasp_obj)

            # Listen to messages on MQTT.
            if domain in ["switch", "light", "media_player"]:
                state_topic = (
                    f"{config[DOMAIN][plate][CONF_TOPIC]}/state/{obj[CONF_OBJID]}"
                )

                _LOGGER.debug("Track MQTT: %s -> %s", state_topic, entity_id)

                hass.data[DOMAIN][plate][state_topic] = entity_id

                async def message_received(msg):
                    """Process MQTT message from plate."""
                    entity_id = hass.data[DOMAIN][plate][msg.topic]
                    _LOGGER.error("%s - %s - %s", msg.topic, entity_id, msg.payload)

                    schema = vol.Schema(
                        {vol.Required("val"): vol.All(int, vol.Range(min=0, max=1))}
                    )
                    cmd = schema(json.loads(msg.payload))

                    service = SERVICE_TURN_OFF
                    if cmd["val"] == 1:
                        service = SERVICE_TURN_ON

                    await hass.services.async_call(
                        "homeassistant", service, {ATTR_ENTITY_ID: entity_id}
                    )

                await hass.components.mqtt.async_subscribe(
                    state_topic, message_received
                )

    return True