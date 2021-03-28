"""HASP-LVGL Common classes."""
import logging
import voluptuous as vol

from homeassistant.core import callback
from homeassistant.helpers.entity import Entity

from .const import HASP_LWT, HASP_ONLINE

_LOGGER = logging.getLogger(__name__)

HASP_LWT_SCHEMA = vol.Schema(vol.Any(*HASP_LWT))


class HASPEntity(Entity):
    """Common HASP-LVGL properties and methods."""

    def __init__(self):
        """Initial values."""
        self._topic = None
        self._available = False

    @property
    def available(self):
        """Return if entity is available."""
        return self._available

    async def refresh(self):
        """Sync properties back to device."""
        raise NotImplementedError("must be implemented by subclass")

    async def async_added_to_hass(self):
        """Run when entity about to be added."""
        await super().async_added_to_hass()

        @callback
        async def lwt_message_received(msg):
            """Process LWT."""

            try:
                message = HASP_LWT_SCHEMA(msg.payload)

                if message == HASP_ONLINE:
                    self._available = True
                    await self.refresh()
                else:
                    self._available = False

                self.async_write_ha_state()

            except vol.error.Invalid as err:
                _LOGGER.error(err)

        await self.hass.components.mqtt.async_subscribe(
            f"{self._topic}/LWT", lwt_message_received
        )
