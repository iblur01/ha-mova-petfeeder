import voluptuous as vol
from homeassistant import config_entries
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME

from .api import MovaCloudAPI
from .const import CONF_COUNTRY, COUNTRIES, DOMAIN


class MovaPetFeederConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(self, user_input=None):
        errors = {}

        if user_input is not None:
            api = MovaCloudAPI(
                user_input[CONF_USERNAME],
                user_input[CONF_PASSWORD],
                user_input[CONF_COUNTRY],
            )
            logged_in = await self.hass.async_add_executor_job(api.login)
            if not logged_in:
                errors["base"] = "invalid_auth"
            else:
                feeders = await self.hass.async_add_executor_job(api.get_feeders)
                if not feeders:
                    errors["base"] = "no_devices"
                else:
                    return self.async_create_entry(
                        title=f"Mova ({user_input[CONF_USERNAME]})",
                        data=user_input,
                    )

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({
                vol.Required(CONF_USERNAME): str,
                vol.Required(CONF_PASSWORD): str,
                vol.Required(CONF_COUNTRY, default="eu"): vol.In(COUNTRIES),
            }),
            errors=errors,
        )
