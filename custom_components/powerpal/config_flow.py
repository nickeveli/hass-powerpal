"""Config flow for Powerpal."""
from __future__ import annotations

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.helpers.aiohttp_client import async_create_clientsession

from .api import PowerpalApiClient, PowerpalAuthenticationError, PowerpalAuthorizationError
from .const import CONF_AUTH_KEY, CONF_DEVICE_ID, DOMAIN


class PowerpalConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Powerpal."""

    VERSION = 1

    async def async_step_user(self, user_input: dict | None = None):
        """Handle the initial step."""
        errors = {}

        if user_input is not None:
            valid, error = await self._test_credentials(
                user_input[CONF_AUTH_KEY], user_input[CONF_DEVICE_ID]
            )
            if valid:
                # Prevent duplicate entries for the same device
                await self.async_set_unique_id(user_input[CONF_DEVICE_ID])
                self._abort_if_unique_id_configured()

                return self.async_create_entry(
                    title=f"Powerpal {user_input[CONF_DEVICE_ID]}",
                    data=user_input,
                )
            errors["base"] = error

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_AUTH_KEY): str,
                    vol.Required(CONF_DEVICE_ID): str,
                }
            ),
            errors=errors,
        )

    async def _test_credentials(self, auth_key: str, device_id: str) -> tuple[bool, str]:
        """Validate credentials by making a test API call."""
        try:
            session = async_create_clientsession(self.hass)
            client = PowerpalApiClient(session, auth_key, device_id)
            await client.get_device_data()
            return True, ""
        except PowerpalAuthenticationError:
            return False, "invalid_auth"
        except PowerpalAuthorizationError:
            return False, "invalid_device"
        except Exception:  # pylint: disable=broad-except
            return False, "cannot_connect"

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: config_entries.ConfigEntry):
        return PowerpalOptionsFlow()


class PowerpalOptionsFlow(config_entries.OptionsFlow):
    """Handle Powerpal options."""

    async def async_step_init(self, user_input: dict | None = None):
        """Manage the options."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        return self.async_show_form(step_id="init")
