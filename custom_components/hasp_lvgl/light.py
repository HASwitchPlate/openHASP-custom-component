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
import homeassistant.util.color as color_util
import voluptuous as vol
from .const import HASP_LWT, HASP_ONLINE

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

HASP_LWT_SCHEMA = vol.Schema(vol.Any(*HASP_LWT))


async def async_setup_platform(hass, _, async_add_entities, discovery_info=None):
    """Set up the HASP LVGL moodlight."""
    if discovery_info is None:
        _LOGGER.error("This platform is only available through discovery")
        return

    async_add_entities(
        [HASPBackLight(hass, discovery_info), HASPMoodLight(hass, discovery_info)]
    )


class HASPLight(LightEntity):
    """Base class for HASP-LVGL lights."""

    def __init__(self, hass, topic, supported):
        """Initialize the light."""
        self._available = False
        self.hass = hass
        self._topic = topic
        self._state = False
        self._name = "light"
        self._supported = supported

    async def async_added_to_hass(self):
        """Run when entity about to be added."""
        await super().async_added_to_hass()

        @callback
        async def lwt_message_received(msg):
            """Process LWT."""
            try:
                message = HASP_LWT_SCHEMA(msg.payload)

                self._available = False

                if message == HASP_ONLINE:
                    self._available = True
                    await self.refresh()

                self.async_write_ha_state()

            except vol.error.Invalid as err:
                _LOGGER.error(err)

        await self.hass.components.mqtt.async_subscribe(
            f"{self._topic}/LWT", lwt_message_received
        )

    async def refresh(self):
        """Sync light properties back to device."""
        raise NotImplementedError("must be implemented by subclass")

    @property
    def available(self):
        """Return if entity is available."""
        return self._available

    @property
    def is_on(self):
        """Return true if device is on."""
        return self._state

    @property
    def supported_features(self):
        """Flag supported features."""
        return self._supported

    @property
    def name(self):
        """Return the name of the light."""
        return self._name


class HASPBackLight(HASPLight):
    """Representation of HASP LVGL Backlight."""

    def __init__(self, hass, conf):
        """Initialize the light."""
        name, topic = conf
        super().__init__(hass, topic, SUPPORT_BRIGHTNESS)
        self._name = f"{name} backlight"
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
                self._available = True
                _LOGGER.debug("backlight = %s", msg.payload)
                message = HASP_BACKLIGHT_SCHEMA(msg.payload)

                if isinstance(message, bool):
                    self._state = message
                else:
                    self._brightness = int(
                        message * 255 / 100
                    )  # convert to HA 0-255 range

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

    async def refresh(self):
        """Sync local state back to plate."""
        cmd_topic = f"{self._topic}/command"
        brightness = int(
            self._brightness * 100 / 255
        )  # convert to HASP-LVGL 0-100 range

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
        """Turn on the moodlight."""
        if ATTR_BRIGHTNESS in kwargs:
            self._brightness = kwargs[ATTR_BRIGHTNESS]
        self._state = True
        await self.refresh()

    async def async_turn_off(self, **kwargs):
        """Turn off the moodlight."""
        self._state = False
        await self.refresh()

    @property
    def brightness(self):
        """Return the brightness of this light between 0..255."""
        return self._brightness


class HASPMoodLight(HASPLight):
    """Representation of HASP LVGL Moodlight."""

    def __init__(self, hass, conf):
        """Initialize the light."""
        name, topic = conf
        super().__init__(hass, topic, SUPPORT_COLOR)
        self._name = f"{name} moodlight"
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
                self._available = True
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

    async def refresh(self):
        """Sync local state back to plate."""
        cmd_topic = f"{self._topic}/command"

        rgb = color_util.color_hs_to_RGB(*self._hs)
        self.hass.components.mqtt.async_publish(
            cmd_topic,
            f'moodlight {{"state":"{self._state}","r":{rgb[0]},"g":{rgb[1]},"b":{rgb[2]}}}',
            qos=0,
            retain=False,
        )

    async def async_turn_on(self, **kwargs):
        """Turn on the moodlight."""
        if ATTR_HS_COLOR in kwargs:
            self._hs = kwargs[ATTR_HS_COLOR]

        self._state = True
        await self.refresh()

    async def async_turn_off(self, **kwargs):
        """Turn off the moodlight."""
        self._state = False
        await self.refresh()

    @property
    def hs_color(self):
        """Return the color property."""
        return self._hs
