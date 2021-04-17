"""Allows to configure a switch using GPIO."""
import json
import logging

from homeassistant.core import callback
import homeassistant.helpers.config_validation as cv
import voluptuous as vol

from .common import HASPToggleEntity
from .const import CONF_PLATE, CONF_RELAYS, CONF_TOPIC

_LOGGER = logging.getLogger(__name__)

HASP_RELAY_SCHEMA = vol.Schema(vol.Any(cv.boolean, vol.Coerce(int)))


# pylint: disable=W0613
async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Set up the HASP LVGL moodlight."""
    if discovery_info is None:
        _LOGGER.error("This platform is only available through discovery")
        return

    relays = discovery_info[CONF_RELAYS]
    plate = discovery_info[CONF_PLATE]
    base_topic = discovery_info[CONF_TOPIC]

    async_add_entities([HASPSwitch(plate, base_topic, gpio) for gpio in relays])


class HASPSwitch(HASPToggleEntity):
    """Representation of an openHASP relay."""

    def __init__(self, plate, topic, gpio):
        """Initialize the relay."""
        super().__init__(plate, topic)
        self._gpio = gpio
        _LOGGER.error("init %s", self.unique_id)

    @property
    def unique_id(self):
        """Return the identifier of the light."""
        return f"{self._plate}/relay/{self._gpio}"

    @property
    def should_poll(self):
        """No polling needed."""
        return False

    async def refresh(self):
        """Sync local state back to plate."""
        cmd_topic = f"{self._topic}/command/relay{self._gpio}"

        if not self._state:
            # Don't do anything before we know the state
            return

        self.hass.components.mqtt.async_publish(
            cmd_topic,
            int(self._state),
            qos=0,
            retain=False,
        )
        self.async_write_ha_state()

    async def async_turn_on(self, **kwargs):
        """Turn the device on."""
        self._state = True
        await self.refresh()

    # pylint disable=R0801
    async def async_turn_off(self, **kwargs):
        """Turn the device off."""
        self._state = False
        await self.refresh()

    async def async_added_to_hass(self):
        """Run when entity about to be added."""
        await super().async_added_to_hass()
        cmd_topic = f"{self._topic}/command/relay{self._gpio}"
        state_topic = f"{self._topic}/state/relay{self._gpio}"

        @callback
        async def state_message_received(msg):
            """Process State."""

            try:
                self._available = True
                message = HASP_RELAY_SCHEMA(json.loads(msg.payload))
                _LOGGER.debug("%s state = %s (%s)", self.name, msg.payload, message)

                self._state = message
                self.async_write_ha_state()

            except vol.error.Invalid as err:
                _LOGGER.error(err)

        await self.hass.components.mqtt.async_subscribe(
            state_topic, state_message_received
        )

        self.hass.components.mqtt.async_publish(cmd_topic, "", qos=0, retain=False)
