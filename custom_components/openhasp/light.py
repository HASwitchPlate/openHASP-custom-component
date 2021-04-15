"""Support for HASP LVGL moodlights."""
import json
import logging

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_HS_COLOR,
    SUPPORT_BRIGHTNESS,
    SUPPORT_COLOR,
    LightEntity,
)
from homeassistant.core import callback
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.restore_state import RestoreEntity
import homeassistant.util.color as color_util

import voluptuous as vol

from .common import HASP_IDLE_SCHEMA, HASPToggleEntity
from .const import (
    ATTR_AWAKE_BRIGHTNESS,
    ATTR_IDLE_BRIGHTNESS,
    CONF_IDLE_BRIGHTNESS,
    CONF_PLATE,
    CONF_TOPIC,
    HASP_IDLE_LONG,
    HASP_IDLE_OFF,
    HASP_IDLE_SHORT,
)

_LOGGER = logging.getLogger(__name__)

HASP_MOODLIGHT_SCHEMA = vol.Schema(
    {
        vol.Required("state"): cv.boolean,
        vol.Required("color"): vol.Schema(
            {vol.Required("r"): int, vol.Required("g"): int, vol.Required("b"): int}
        ),
    },
)

HASP_BACKLIGHT_SCHEMA = vol.Schema(vol.Any(cv.boolean, vol.Coerce(int)))


# pylint: disable=W0613
async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Set up the HASP LVGL moodlight."""
    if discovery_info is None:
        _LOGGER.error("This platform is only available through discovery")
        return

    plate = discovery_info[CONF_PLATE]
    base_topic = discovery_info[CONF_TOPIC]
    brightness = discovery_info[CONF_IDLE_BRIGHTNESS]

    async_add_entities(
        [HASPBackLight(plate, base_topic, brightness), HASPMoodLight(plate, base_topic)]
    )


class HASPBackLight(HASPToggleEntity, LightEntity, RestoreEntity):
    """Representation of HASP LVGL Backlight."""

    def __init__(self, plate, topic, brightness):
        """Initialize the light."""
        super().__init__(plate, topic)
        self._awake_brightness = None
        self._brightness = None
        self._idle_brightness = brightness

    @property
    def supported_features(self):
        """Flag supported features."""
        return SUPPORT_BRIGHTNESS

    @property
    def unique_id(self):
        """Return the identifier of the light."""
        return f"{self._plate} backlight"

    @property
    def extra_state_attributes(self):
        """Return the state attributes."""
        attributes = {
            ATTR_AWAKE_BRIGHTNESS: self._awake_brightness,
            ATTR_IDLE_BRIGHTNESS: self._idle_brightness,
        }

        return attributes

    @property
    def brightness(self):
        """Return the brightness of this light between 0..255."""
        return self._brightness

    async def async_added_to_hass(self):
        """Run when entity about to be added."""
        await super().async_added_to_hass()

        state = await self.async_get_last_state()
        if state:
            self._state = state.state
            self._brightness = state.attributes.get(ATTR_BRIGHTNESS)
            self._awake_brightness = state.attributes.get(ATTR_AWAKE_BRIGHTNESS, 255)
            _LOGGER.debug("Restoring awake_brightness = %s", self._awake_brightness)

        await self.async_listen_idleness()

        cmd_topic = f"{self._topic}/command"
        light_state_topic = f"{self._topic}/state/light"
        dim_state_topic = f"{self._topic}/state/dim"

        @callback
        async def backlight_message_received(msg):
            """Process Backlight State."""

            try:
                self._available = True
                _LOGGER.debug("backlight %s: %s", msg.topic, msg.payload)
                message = HASP_BACKLIGHT_SCHEMA(msg.payload)

                if isinstance(message, bool):
                    self._state = message
                else:
                    self._brightness = message

                self.async_write_ha_state()

            except vol.error.Invalid as err:
                _LOGGER.error(err)

        await self.hass.components.mqtt.async_subscribe(
            light_state_topic, backlight_message_received
        )
        await self.hass.components.mqtt.async_subscribe(
            dim_state_topic, backlight_message_received
        )
        self.hass.components.mqtt.async_publish(
            cmd_topic, 'json ["light", "dim"]', qos=0, retain=False
        )

    async def async_listen_idleness(self):
        """Listen to messages on MQTT for HASP idleness."""
        state_topic = f"{self._topic}/state/idle"
        cmd_topic = f"{self._topic}/command"

        @callback
        async def idle_message_received(msg):
            """Process MQTT message from plate."""
            message = HASP_IDLE_SCHEMA(msg.payload)

            if message == HASP_IDLE_OFF:
                dim = self._awake_brightness
                backlight = 1
            elif message == HASP_IDLE_SHORT:
                dim = self._idle_brightness
                backlight = 1
            elif message == HASP_IDLE_LONG:
                dim = self._awake_brightness
                backlight = 0
            else:
                return

            _LOGGER.debug(
                "Idle state is %s - Dimming to %s; Backlight to %s",
                message,
                dim,
                backlight,
            )

            dim_str = ""
            if dim:
                dim_str = f', "dim {dim}"'
            self.hass.components.mqtt.async_publish(
                cmd_topic,
                f'json ["light {backlight}"{dim_str}]',
                qos=0,
                retain=False,
            )
            self.async_write_ha_state()

        await self.hass.components.mqtt.async_subscribe(
            state_topic, idle_message_received
        )

    async def refresh(self):
        """Sync local state back to plate."""
        cmd_topic = f"{self._topic}/command"
        brightness = self._brightness

        self.hass.components.mqtt.async_publish(
            cmd_topic,
            f"dim {brightness}",
            qos=0,
            retain=False,
        )

        self.hass.components.mqtt.async_publish(
            cmd_topic,
            f"light {self._state}",
            qos=0,
            retain=False,
        )

    async def async_turn_on(self, **kwargs):
        """Turn on the backlight."""
        if ATTR_BRIGHTNESS in kwargs:
            self._brightness = kwargs[ATTR_BRIGHTNESS]
            self._awake_brightness = (
                self._brightness
            )  # save this value for later recall
        self._state = True
        await self.refresh()

    async def async_turn_off(self, **kwargs):
        """Turn off the backlight."""
        self._state = False
        await self.refresh()


class HASPMoodLight(HASPToggleEntity, LightEntity):
    """Representation of HASP LVGL Moodlight."""

    def __init__(self, plate, topic):
        """Initialize the light."""
        super().__init__(plate, topic)
        self._hs = None

    @property
    def supported_features(self):
        """Flag supported features."""
        return SUPPORT_COLOR

    @property
    def unique_id(self):
        """Return the identifier of the light."""
        return f"{self._plate} moodlight"

    @property
    def hs_color(self):
        """Return the color property."""
        return self._hs

    async def async_added_to_hass(self):
        """Run when entity about to be added."""
        await super().async_added_to_hass()

        cmd_topic = f"{self._topic}/command"
        state_topic = f"{self._topic}/state/moodlight"

        @callback
        async def moodlight_message_received(msg):
            """Process Moodlight State."""

            try:
                self._available = True
                _LOGGER.debug("moodlight %s: %s", msg.topic, msg.payload)
                message = HASP_MOODLIGHT_SCHEMA(json.loads(msg.payload))

                self._state = message["state"]
                self._hs = color_util.color_RGB_to_hs(
                    message["color"]["r"], message["color"]["g"], message["color"]["b"]
                )
                self.async_write_ha_state()

            except vol.error.Invalid as err:
                _LOGGER.error(err)

        await self.hass.components.mqtt.async_subscribe(
            state_topic, moodlight_message_received
        )

        self.hass.components.mqtt.async_publish(
            cmd_topic, "moodlight", qos=0, retain=False
        )

    async def refresh(self):
        """Sync local state back to plate."""
        cmd_topic = f"{self._topic}/command"

        colors = ""
        if self._hs:
            rgb = color_util.color_hs_to_RGB(*self._hs)
            colors = f', "r":{rgb[0]},"g":{rgb[1]},"b":{rgb[2]}'

        _LOGGER.debug("refresh %s - %s", self._topic, colors)
        self.hass.components.mqtt.async_publish(
            cmd_topic,
            f'moodlight {{"state":"{self._state}"{colors}}}',
            qos=0,
            retain=False,
        )

    async def async_turn_on(self, **kwargs):
        """Turn on the moodlight."""
        if ATTR_HS_COLOR in kwargs:
            self._hs = kwargs[ATTR_HS_COLOR]

        self._state = True
        _LOGGER.debug("Turn on %s - %s", self._topic, self._hs)
        await self.refresh()

    async def async_turn_off(self, **kwargs):
        """Turn off the moodlight."""
        self._state = False
        _LOGGER.debug("Turn off %s", self._topic)
        await self.refresh()
