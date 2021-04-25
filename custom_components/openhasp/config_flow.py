"""Config flow to configure OpenHASP component."""
import json
from homeassistant import config_entries
from homeassistant.const import CONF_NAME
from homeassistant.components.mqtt import valid_subscribe_topic
import homeassistant.helpers.config_validation as cv
from homeassistant.core import callback

import voluptuous as vol

from .const import (
    CONF_RELAYS,
    CONF_HWID,
    CONF_IDLE_BRIGHTNESS,
    CONF_TOPIC,
    CONF_NODE,
    DEFAULT_IDLE_BRIGHNESS,
    DOMAIN,
    DISCOVERED_MANUFACTURER,
    DISCOVERED_MODEL,
    DISCOVERED_VERSION,
)


@config_entries.HANDLERS.register(DOMAIN)
class OpenHASPFlowHandler(config_entries.ConfigFlow):
    """Config flow for OpenHASP component."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_LOCAL_PUSH

    def __init__(self):
        """Init OpenHASPFlowHandler."""
        self._errors = {}
        self.config_data = {
            DISCOVERED_MANUFACTURER: "openHASP",
            DISCOVERED_MODEL: None,
            CONF_RELAYS: [],
        }

    async def async_step_mqtt(self, discovery_info=None):
        """Handle a flow initialized by MQTT discovery."""

        _discovered = json.loads(discovery_info.payload)

        name = _discovered["node"]
        hwid = _discovered[CONF_HWID]
        await self.async_set_unique_id(hwid)
        self._abort_if_unique_id_configured()

        self.config_data[CONF_HWID] = hwid
        self.config_data[CONF_NODE] = self.config_data[CONF_NAME] = name
        self.config_data[CONF_TOPIC] = discovery_info.topic.split("/")[0]
        self.config_data[DISCOVERED_VERSION] = _discovered.get(DISCOVERED_VERSION)
        self.config_data[DISCOVERED_MANUFACTURER] = _discovered.get(DISCOVERED_MANUFACTURER)
        self.config_data[DISCOVERED_MODEL] = _discovered.get(DISCOVERED_MODEL)
        self.config_data["num_pages"] = _discovered.get("num_pages")

        return await self.async_step_personalize()

    async def async_step_personalize(self, user_input=None):
        """Handle a flow initialized by the user."""
        self._errors = {}

        if user_input is not None:
            self.config_data = {**self.config_data, **user_input}

            if self.config_data[
                CONF_NAME
            ] not in self.hass.config_entries.async_entries(DOMAIN):
                # Remove / from base topic
                if user_input[CONF_TOPIC].endswith("/"):
                    user_input[CONF_TOPIC] = user_input[CONF_TOPIC][:-1]

                self.config_data[
                    CONF_TOPIC
                ] = f"{user_input[CONF_TOPIC]}/{self.config_data[CONF_NODE]}"

                try:
                    valid_subscribe_topic(self.config_data[CONF_TOPIC])
                except vol.Invalid:
                    return self.async_abort(reason="invalid_discovery_info")

                return self.async_create_entry(
                    title=user_input[CONF_NAME], data=self.config_data
                )

            self._errors[CONF_NAME] = "name_exists"

        available_gpios = {str(n): n for n in range(20, 30)}

        return self.async_show_form(
            step_id="personalize",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_TOPIC, default=self.config_data.get(CONF_TOPIC, "hasp")
                    ): str,
                    vol.Required(
                        CONF_NAME, default=self.config_data.get(CONF_NAME)
                    ): str,
                    vol.Optional(
                        CONF_IDLE_BRIGHTNESS, default=DEFAULT_IDLE_BRIGHNESS
                    ): vol.All(int, vol.Range(min=0, max=255)),
                    vol.Optional(
                        CONF_RELAYS, default=self.config_data.get(CONF_RELAYS)
                    ): cv.multi_select(available_gpios),
                }
            ),
            errors=self._errors,
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        return OpenHASPOptionsFlowHandler(config_entry)


class OpenHASPOptionsFlowHandler(config_entries.OptionsFlow):
    """ConfigOptions flow for openHASP."""

    def __init__(self, config_entry):
        """Initialize openHASP options flow."""
        self.config_entry = config_entry

    async def async_step_init(self, user_input=None):
        """Manage the options."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Optional(
                        CONF_IDLE_BRIGHTNESS,
                        default=self.config_entry.options.get(
                            CONF_IDLE_BRIGHTNESS,
                            self.config_entry.data[CONF_IDLE_BRIGHTNESS],
                        ),
                    ): vol.All(int, vol.Range(min=0, max=255)),
                }
            ),
        )
