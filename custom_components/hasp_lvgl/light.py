"""Support for HASP LVGL moodlights."""
import json
import logging
from math import ceil

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_HS_COLOR,
    SUPPORT_BRIGHTNESS,
    SUPPORT_COLOR,
    LightEntity,
)
from homeassistant.core import callback
import homeassistant.helpers.config_validation as cv
import homeassistant.util.color as color_util
import voluptuous as vol

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


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Set up the HASP LVGL moodlight."""
    if discovery_info is None:
        _LOGGER.error("This platform is only available through discovery")
        return

    async_add_entities(
        [HASPBackLight(hass, discovery_info), HASPMoodLight(hass, discovery_info)]
    )


class HASPBackLight(LightEntity):
    """Representation of HASP LVGL Backlight."""

    def __init__(self, hass, conf):
        """Initialize the light."""
        name, topic = conf
        self.hass = hass
        self._name = f"{name} backlight"
        self._topic = f"{topic}"
        self._state = False
        self._brightness = 0

    async def async_added_to_hass(self):
        """Run when entity about to be added."""
        await super().async_added_to_hass()
        cmd_topic = f"{self._topic}/command"
        light_state_topic = f"{self._topic}/state/light"
        dim_state_topic = f"{self._topic}/state/dim"

        @callback
        async def backlight_message_received(msg):
            """Process Backlight State."""

            try:
                _LOGGER.debug("backlight = %s", msg.payload)
                message = HASP_BACKLIGHT_SCHEMA(msg.payload)

                if isinstance(message, bool):
                    self._state = message
                else:
                    self._brightness = ceil(message * 255 / 100)

                self.async_write_ha_state()

            except vol.error.Invalid as err:
                _LOGGER.error(err)

        await self.hass.components.mqtt.async_subscribe(
            light_state_topic, backlight_message_received
        )
        await self.hass.components.mqtt.async_subscribe(
            dim_state_topic, backlight_message_received
        )
        self.hass.components.mqtt.async_publish(cmd_topic, "light", qos=0, retain=False)
        self.hass.components.mqtt.async_publish(cmd_topic, "dim", qos=0, retain=False)

    async def async_turn_on(self, **kwargs):
        """Turn on the moodlight."""
        cmd_topic = f"{self._topic}/command"

        if ATTR_BRIGHTNESS in kwargs:
            self._brightness = ceil(kwargs[ATTR_BRIGHTNESS] * 100 / 255)
            self.hass.components.mqtt.async_publish(
                cmd_topic,
                f"dim {self._brightness}",
                qos=0,
                retain=False,
            )

        self.hass.components.mqtt.async_publish(
            cmd_topic,
            "light on",
            qos=0,
            retain=False,
        )

    async def async_turn_off(self, **kwargs):
        """Turn off the moodlight."""
        cmd_topic = f"{self._topic}/command"

        self.hass.components.mqtt.async_publish(
            cmd_topic, "light off", qos=0, retain=False
        )

    @property
    def is_on(self):
        """Return true if device is on."""
        return self._state

    @property
    def brightness(self):
        """Return the brightness of this light between 0..255."""
        return self._brightness

    @property
    def name(self):
        """Return the name of the device if any."""
        return self._name

    @property
    def supported_features(self):
        """Flag supported features."""
        return SUPPORT_BRIGHTNESS

    @property
    def unique_id(self):
        """Return the ID of this light."""
        return self._name


class HASPMoodLight(LightEntity):
    """Representation of HASP LVGL Moodlight."""

    def __init__(self, hass, conf):
        """Initialize the light."""
        name, topic = conf
        self.hass = hass
        self._name = f"{name} moodlight"
        self._topic = f"{topic}"
        self._state = False
        self._hs = [0, 0]

    async def async_added_to_hass(self):
        """Run when entity about to be added."""
        await super().async_added_to_hass()
        cmd_topic = f"{self._topic}/command"
        state_topic = f"{self._topic}/state/moodlight"

        @callback
        async def moodlight_message_received(msg):
            """Process Moodlight State."""

            try:
                _LOGGER.debug("moodlight = %s", msg.payload)
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

    async def async_turn_on(self, **kwargs):
        """Turn on the moodlight."""
        cmd_topic = f"{self._topic}/command"

        if ATTR_HS_COLOR in kwargs:
            self._hs = kwargs[ATTR_HS_COLOR]

        rgb = color_util.color_hs_to_RGB(*self._hs)
        self.hass.components.mqtt.async_publish(
            cmd_topic,
            f'moodlight {{"state":"on","r":{rgb[0]},"g":{rgb[1]},"b":{rgb[2]}}}',
            qos=0,
            retain=False,
        )

    async def async_turn_off(self, **kwargs):
        """Turn off the moodlight."""
        cmd_topic = f"{self._topic}/command"

        self.hass.components.mqtt.async_publish(
            cmd_topic, 'moodlight {"state":"off"}', qos=0, retain=False
        )

    @property
    def is_on(self):
        """Return true if device is on."""
        return self._state

    @property
    def hs_color(self):
        """Return the color property."""
        return self._hs

    @property
    def name(self):
        """Return the name of the device if any."""
        return self._name

    @property
    def supported_features(self):
        """Flag supported features."""
        return SUPPORT_COLOR

    @property
    def unique_id(self):
        """Return the ID of this light."""
        return self._name
