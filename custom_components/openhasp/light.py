"""Support for HASP LVGL moodlights."""
import json
import logging
from typing import Callable

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_HS_COLOR,
    SUPPORT_BRIGHTNESS,
    SUPPORT_COLOR,
    LightEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.restore_state import RestoreEntity
import homeassistant.util.color as color_util
import voluptuous as vol

from .common import HASP_IDLE_SCHEMA, HASPToggleEntity
from .const import (
    ATTR_AWAKE_BRIGHTNESS,
    ATTR_IDLE_BRIGHTNESS,
    CONF_DIMLIGHTS,
    CONF_HWID,
    CONF_IDLE_BRIGHTNESS,
    CONF_LIGHTS,
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
            {
                vol.Required("r"): int,
                vol.Required("g"): int,
                vol.Required("b"): int,
                vol.Required("brightness"): int,
            }
        ),
    },
)

HASP_BACKLIGHT_SCHEMA = vol.Schema(vol.Any(cv.boolean, vol.Coerce(int)))

HASP_LIGHT_SCHEMA = vol.Schema(
    {
        vol.Required("state"): vol.Coerce(int),
        vol.Optional("val"): vol.All(int, vol.Range(min=0, max=255)),
    }
)

# pylint: disable=R0801, W0613
async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: Callable
):
    """Set up Plate Light sensors based on a config entry."""

    async_add_entities(
        [
            HASPBackLight(
                entry.data[CONF_HWID],
                entry.data[CONF_TOPIC],
                entry.options.get(
                    CONF_IDLE_BRIGHTNESS, entry.data[CONF_IDLE_BRIGHTNESS]
                ),
            ),
            HASPMoodLight(entry.data[CONF_HWID], entry.data[CONF_TOPIC]),
        ]
        + [
            HASPLight(
                entry.data[CONF_HWID],
                entry.data[CONF_TOPIC],
                gpio,
            )
            for gpio in entry.data[CONF_LIGHTS]
        ]
        + [
            HASPDimmableLight(
                entry.data[CONF_HWID],
                entry.data[CONF_TOPIC],
                gpio,
            )
            for gpio in entry.data[CONF_DIMLIGHTS]
        ]
    )

    return True


class HASPLight(HASPToggleEntity, LightEntity):
    """Representation of openHASP Light."""

    def __init__(self, hwid, topic, gpio):
        """Initialize the light."""
        super().__init__(hwid, topic)
        self._gpio = gpio

    @property
    def unique_id(self):
        """Return the identifier of the light."""
        return f"{self._hwid} light {self._gpio}"

    async def async_turn_on(self, **kwargs):
        """Turn on the backlight."""
        self._state = True
        await self.refresh()

    async def async_turn_off(self, **kwargs):
        """Turn off the backlight."""
        self._state = False
        await self.refresh()

    async def refresh(self):
        """Sync local state back to plate."""
        cmd_topic = f"{self._topic}/command/output{self._gpio}"

        self.hass.components.mqtt.async_publish(
            cmd_topic,
            json.dumps(
                HASP_LIGHT_SCHEMA({"state": int(self._state), "val": int(self._state)})
            ),
            qos=0,
            retain=False,
        )
        self.async_write_ha_state()

    async def async_added_to_hass(self):
        """Run when entity about to be added."""
        await super().async_added_to_hass()
        cmd_topic = f"{self._topic}/command/output{self._gpio}"
        state_topic = f"{self._topic}/state/output{self._gpio}"

        @callback
        async def state_message_received(msg):
            """Process State."""

            try:
                self._available = True
                message = HASP_LIGHT_SCHEMA(json.loads(msg.payload))
                _LOGGER.debug("%s state = %s (%s)", self.name, msg.payload, message)

                self._state = message["state"]
                self.async_write_ha_state()

            except vol.error.Invalid as err:
                _LOGGER.error(err)

        self._subscriptions.append(
            await self.hass.components.mqtt.async_subscribe(
                state_topic, state_message_received
            )
        )

        self.hass.components.mqtt.async_publish(cmd_topic, "", qos=0, retain=False)


class HASPDimmableLight(HASPToggleEntity, LightEntity):
    """Representation of openHASP Light."""

    def __init__(self, hwid, topic, gpio):
        """Initialize the dimmable light."""
        super().__init__(hwid, topic)
        self._brightness = None
        self._gpio = gpio

    @property
    def supported_features(self):
        """Flag supported features."""
        return SUPPORT_BRIGHTNESS

    @property
    def unique_id(self):
        """Return the identifier of the light."""
        return f"{self._hwid} dimmable light {self._gpio}"

    @property
    def brightness(self):
        """Return the brightness of this light between 0..255."""
        return self._brightness

    async def async_turn_on(self, **kwargs):
        """Turn on the dimmable light."""
        if ATTR_BRIGHTNESS in kwargs:
            self._brightness = kwargs[ATTR_BRIGHTNESS]
        self._state = True
        await self.refresh()

    async def async_turn_off(self, **kwargs):
        """Turn off the dimmable light."""
        self._state = False
        await self.refresh()

    async def refresh(self):
        """Sync local state back to plate."""
        cmd_topic = f"{self._topic}/command/output{self._gpio}"

        _LOGGER.debug(
            "refresh dim %s state = %s (%s)",
            self.name,
            int(self._state),
            self._brightness,
        )

        print(
            json.dumps(
                HASP_LIGHT_SCHEMA({"state": int(self._state), "val": self._brightness})
            )
        )

        self.hass.components.mqtt.async_publish(
            cmd_topic,
            json.dumps(
                HASP_LIGHT_SCHEMA({"state": int(self._state), "val": self._brightness})
            ),
            qos=0,
            retain=False,
        )
        self.async_write_ha_state()

    async def async_added_to_hass(self):
        """Run when entity about to be added."""
        await super().async_added_to_hass()
        cmd_topic = f"{self._topic}/command/output{self._gpio}"
        state_topic = f"{self._topic}/state/output{self._gpio}"

        @callback
        async def state_message_received(msg):
            """Process State."""

            try:
                self._available = True
                message = HASP_LIGHT_SCHEMA(json.loads(msg.payload))
                _LOGGER.debug(
                    "dimmable %s state = %s (%s)", self.name, msg.payload, message
                )

                self._state = message["state"]
                self._brightness = message["val"]
                self.async_write_ha_state()

            except vol.error.Invalid as err:
                _LOGGER.error(err)

        self._subscriptions.append(
            await self.hass.components.mqtt.async_subscribe(
                state_topic, state_message_received
            )
        )

        self.hass.components.mqtt.async_publish(cmd_topic, "", qos=0, retain=False)


class HASPBackLight(HASPToggleEntity, LightEntity, RestoreEntity):
    """Representation of HASP LVGL Backlight."""

    def __init__(self, hwid, topic, brightness):
        """Initialize the light."""
        super().__init__(hwid, topic)
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
        return f"{self._hwid} backlight"

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
            _LOGGER.debug(
                "Restoring self.brigthness = %s; awake_brightness = %s",
                self._brightness,
                self._awake_brightness,
            )
            if not self._brightness:
                self._brightness = self._awake_brightness

        await self.async_listen_idleness()

        cmd_topic = f"{self._topic}/command"
        light_state_topic = f"{self._topic}/state/light"
        dim_state_topic = f"{self._topic}/state/dim"

        @callback
        async def backlight_message_received(msg):
            """Process Backlight State."""

            try:
                self._available = True
                _LOGGER.debug("received backlight %s: %s", msg.topic, msg.payload)
                message = HASP_BACKLIGHT_SCHEMA(msg.payload)

                if isinstance(message, bool):
                    self._state = message
                else:
                    self._brightness = message

                self.async_write_ha_state()

            except vol.error.Invalid as err:
                _LOGGER.error("While proccessing backlight: %s", err)

        self._subscriptions.append(
            await self.hass.components.mqtt.async_subscribe(
                light_state_topic, backlight_message_received
            )
        )

        self._subscriptions.append(
            await self.hass.components.mqtt.async_subscribe(
                dim_state_topic, backlight_message_received
            )
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

            self.hass.components.mqtt.async_publish(
                cmd_topic,
                f'json ["light {backlight}", "dim {dim}"]',
                qos=0,
                retain=False,
            )
            self.async_write_ha_state()

        self._subscriptions.append(
            await self.hass.components.mqtt.async_subscribe(
                state_topic, idle_message_received
            )
        )

    async def refresh(self):
        """Sync local state back to plate."""
        cmd_topic = f"{self._topic}/command"

        _LOGGER.debug(
            "refresh() backlight brightness = %s, light = %s",
            self._brightness,
            self._state,
        )

        self.hass.components.mqtt.async_publish(
            cmd_topic,
            f'json ["light {self._state}", "dim {self._brightness}"]',
            qos=0,
            retain=False,
        )
        self.async_write_ha_state()

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

    def __init__(self, hwid, topic):
        """Initialize the light."""
        super().__init__(hwid, topic)
        self._hs = None

    @property
    def supported_features(self):
        """Flag supported features."""
        return SUPPORT_COLOR

    @property
    def unique_id(self):
        """Return the identifier of the light."""
        return f"{self._hwid} moodlight"

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
                _LOGGER.error("While proccessing moodlight: %s", err)

        self._subscriptions.append(
            await self.hass.components.mqtt.async_subscribe(
                state_topic, moodlight_message_received
            )
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
