"""Config flow to configure OpenHASP component."""
import json
from homeassistant import config_entries
from homeassistant.const import CONF_NAME
from homeassistant.components.mqtt import valid_subscribe_topic
import voluptuous as vol

from .const import (
    CONF_IDLE_BRIGHTNESS,
    CONF_TOPIC,
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
        self.config_data = {DISCOVERED_MANUFACTURER: "openHASP", DISCOVERED_MODEL: None}

    async def async_step_mqtt(self, discovery_info=None):
        """Handle a flow initialized by MQTT discovery."""

        _discovered = json.loads(discovery_info.payload)

        name = discovery_info.topic.split("/")[1]
        await self.async_set_unique_id(name)
        self._abort_if_unique_id_configured()

        self.config_data[CONF_NAME] = name
        self.config_data[CONF_TOPIC] = discovery_info.topic.split("/")[0]
        self.config_data[DISCOVERED_VERSION] = _discovered.get(DISCOVERED_VERSION)

        return await self.async_step_user()

    async def async_step_user(self, user_input=None):
        """Handle a flow initialized by the user."""
        self._errors = {}

        if user_input is not None:
            self.config_data = {**self.config_data, **user_input}

            await self.async_set_unique_id(self.config_data[CONF_NAME])
            self._abort_if_unique_id_configured()

            if self.config_data[
                CONF_NAME
            ] not in self.hass.config_entries.async_entries(DOMAIN):
                # Remove / from base topic
                if user_input[CONF_TOPIC].endswith("/"):
                    user_input[CONF_TOPIC] = user_input[CONF_TOPIC][:-1]

                self.config_data[
                    CONF_TOPIC
                ] = f"{user_input[CONF_TOPIC]}/{user_input[CONF_NAME]}"

                try:
                    valid_subscribe_topic(self.config_data[CONF_TOPIC])
                except vol.Invalid:
                    return self.async_abort(reason="invalid_discovery_info")

                return self.async_create_entry(
                    title=user_input[CONF_NAME], data=self.config_data
                )

            self._errors[CONF_NAME] = "name_exists"

        return self.async_show_form(
            step_id="user",
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
                }
            ),
            errors=self._errors,
        )
