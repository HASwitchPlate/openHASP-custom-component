"""Support for current page numbers."""
import logging

from homeassistant.components.number import NumberEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.const import CONF_NAME

from .common import HASPEntity
from .const import CONF_HWID, CONF_TOPIC

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities
):
    """Set up Plate Relays as switch based on a config entry."""

    async_add_entities(
        [
            HASPPageNumber(
                entry.data[CONF_NAME],
                entry.data[CONF_HWID],
                entry.data[CONF_TOPIC],
            )
        ]
    )

    return True


class HASPPageNumber(HASPEntity, NumberEntity):
    """Representation of page number."""

    _attr_entity_category = ENTITY_CATEGORY_CONFIG
    _attr_icon = "mdi:numeric-1-box-multiple-outline"
    _attr_max_value = 12
    _attr_min_value = 1

    def __init__(self, name, hwid, topic) -> None:
        """Initialize the page number."""
        super().__init__(name, hwid, topic, None)
        self._page = None

    async def refresh(self):
        """Sync local state back to plate."""
        if self._page is None:
            # Don't do anything before we know the state
            return

        await self.hass.components.mqtt.async_publish(
            self.hass,
            f"{self._topic}/command/page",
            self._page,
            qos=0,
            retain=False,
        )
        self.async_write_ha_state()

    async def async_added_to_hass(self):
        """Run when entity about to be added."""
        await super().async_added_to_hass()

        @callback
        async def page_state_message_received(msg):
            """Process State."""

            self._available = True
            _LOGGER.debug("%s current page = %s", self.name, msg.payload)

            self._page = int(msg.payload)
            self.async_write_ha_state()

        self._subscriptions.append(
            await self.hass.components.mqtt.async_subscribe(
                f"{self._topic}/state/page", page_state_message_received
            )
        )

    @property
    def value(self) -> int:
        """Return the current page numaber."""
        return self._page

    async def async_set_value(self, value: float) -> None:
        """Set the perfume amount."""
        if not value.is_integer():
            raise ValueError(f"Can't set the page to {value}. Page must be an integer.")
        self._page = int(value)
        await self.refresh()
