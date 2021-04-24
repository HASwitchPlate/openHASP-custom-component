"""Config flow to configure OpenHASP component."""
from homeassistant import config_entries
from homeassistant.const import CONF_NAME
import voluptuous as vol

from .const import CONF_IDLE_BRIGHTNESS, CONF_TOPIC, DEFAULT_IDLE_BRIGHNESS, DOMAIN


@config_entries.HANDLERS.register(DOMAIN)
class OpenHASPFlowHandler(config_entries.ConfigFlow):
    """Config flow for OpenHASP component."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_LOCAL_PUSH

    def __init__(self):
        """Init OpenHASPFlowHandler."""
        self._errors = {}

    async def async_step_user(self, user_input=None):
        """Handle a flow initialized by the user."""
        self._errors = {}

        if user_input is not None:

            await self.async_set_unique_id(user_input[CONF_NAME])
            self._abort_if_unique_id_configured()

            if user_input[CONF_NAME] not in self.hass.config_entries.async_entries(
                DOMAIN
            ):
                user_input[
                    CONF_TOPIC
                ] = f"{user_input[CONF_TOPIC]}{user_input[CONF_NAME]}"
                return self.async_create_entry(
                    title=user_input[CONF_NAME], data=user_input
                )

            self._errors[CONF_NAME] = "name_exists"

        return await self._show_config_form()

    async def _show_config_form(
        self, name=None, base_topic="hasp/", idle_brightness=DEFAULT_IDLE_BRIGHNESS
    ):
        """Show the configuration form to edit location data."""
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_TOPIC, default=base_topic): str,
                    vol.Required(CONF_NAME, default=name): str,
                    vol.Optional(
                        CONF_IDLE_BRIGHTNESS, default=idle_brightness
                    ): vol.All(int, vol.Range(min=0, max=255)),
                }
            ),
            errors=self._errors,
        )
