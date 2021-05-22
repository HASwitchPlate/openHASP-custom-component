"""Allows to configure a switch using GPIO."""
import json
import logging
from typing import Callable

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
import homeassistant.helpers.config_validation as cv
import voluptuous as vol

from .common import HASPToggleEntity
from .const import CONF_HWID, CONF_RELAYS, CONF_TOPIC

_LOGGER = logging.getLogger(__name__)


HASP_RELAY_SCHEMA = vol.Schema(
    {
        vol.Required("state"): vol.Any(cv.boolean, vol.Coerce(int)),
        vol.Optional("val"): int,
    }
)


# pylint: disable=R0801, W0613
async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: Callable
):
    """Set up Plate Relays as switch based on a config entry."""

    async_add_entities(
        [
            HASPSwitch(
                entry.data[CONF_HWID],
                entry.data[CONF_TOPIC],
                gpio,
            )
            for gpio in entry.data[CONF_RELAYS]
        ]
    )

    return True


class HASPSwitch(HASPToggleEntity):
    """Representation of an openHASP relay."""

    def __init__(self, hwid, topic, gpio):
        """Initialize the relay."""
        super().__init__(hwid, topic)
        self._gpio = gpio
        _LOGGER.error("init %s", self.unique_id)

    @property
    def unique_id(self):
        """Return the identifier of the light."""
        return f"{self._hwid} switch {self._gpio}"

    async def refresh(self):
        """Sync local state back to plate."""
        cmd_topic = f"{self._topic}/command/output{self._gpio}"

        if self._state is None:
            # Don't do anything before we know the state
            return

        self.hass.components.mqtt.async_publish(
            cmd_topic,
            json.dumps(
                HASP_RELAY_SCHEMA({"state": int(self._state), "val": int(self._state)})
            ),
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
        cmd_topic = f"{self._topic}/command/output{self._gpio}"
        state_topic = f"{self._topic}/state/output{self._gpio}"

        @callback
        async def state_message_received(msg):
            """Process State."""

            try:
                self._available = True
                message = HASP_RELAY_SCHEMA(json.loads(msg.payload))
                _LOGGER.debug(
                    "%s state = %s (%s)", self.unique_id, msg.payload, message
                )

                self._state = message["state"]
                self.async_write_ha_state()

            except vol.error.Invalid as err:
                _LOGGER.error(err)

        await self.hass.components.mqtt.async_subscribe(
            state_topic, state_message_received
        )

        self.hass.components.mqtt.async_publish(cmd_topic, "", qos=0, retain=False)
