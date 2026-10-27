"""Config, reauth and options flows for Mova Pet Feeder."""

from __future__ import annotations

import logging
from collections.abc import Mapping
from typing import Any

import voluptuous as vol
from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import (
    BooleanSelector,
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    SelectSelector,
    SelectSelectorConfig,
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)

from .api import MovaClient
from .const import (
    CONF_COUNTRY,
    CONF_DEFAULT_PORTIONS,
    CONF_ENABLE_SCHEDULE_WRITE,
    CONF_PASSWORD_HASH,
    CONF_SCAN_INTERVAL,
    COUNTRIES,
    DEFAULT_PORTIONS,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    MAX_MANUAL_PORTIONS,
    MAX_SCAN_INTERVAL,
    MIN_SCAN_INTERVAL,
)
from .models import MovaError, config_error_key, hash_password

_LOGGER = logging.getLogger(__name__)

_PASSWORD = TextSelector(TextSelectorConfig(type=TextSelectorType.PASSWORD))


class MovaPetFeederConfigFlow(ConfigFlow, domain=DOMAIN):
    VERSION = 2

    async def _async_check(self, username: str, password_hash: str, country: str) -> str | None:
        """Log in and list feeders; return an error key or None."""
        client = MovaClient(async_get_clientsession(self.hass), username, password_hash, country)
        try:
            await client.login()
            devices = await client.list_devices()
        except MovaError as err:
            # Exception messages are already masked (safe_detail / HTTP status only).
            _LOGGER.warning(
                "Mova login check failed: %s (code=%s) %s",
                type(err).__name__, getattr(err, "code", None), err,
            )
            return config_error_key(err)
        except Exception as err:
            _LOGGER.exception("Unexpected error during Mova login")
            return config_error_key(err)
        return config_error_key(None, devices)

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            username = user_input[CONF_USERNAME].strip()
            await self.async_set_unique_id(username.lower())
            self._abort_if_unique_id_configured()
            password_hash = hash_password(user_input[CONF_PASSWORD])
            error = await self._async_check(username, password_hash, user_input[CONF_COUNTRY])
            if error is None:
                return self.async_create_entry(
                    title=f"Mova ({username})",
                    data={
                        CONF_USERNAME: username,
                        CONF_PASSWORD_HASH: password_hash,
                        CONF_COUNTRY: user_input[CONF_COUNTRY],
                    },
                )
            errors["base"] = error

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_USERNAME): str,
                    vol.Required(CONF_PASSWORD): _PASSWORD,
                    vol.Required(CONF_COUNTRY, default="eu"): SelectSelector(
                        SelectSelectorConfig(options=COUNTRIES)
                    ),
                }
            ),
            errors=errors,
        )

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        entry = self._get_reauth_entry()
        errors: dict[str, str] = {}
        if user_input is not None:
            password_hash = hash_password(user_input[CONF_PASSWORD])
            error = await self._async_check(
                entry.data[CONF_USERNAME], password_hash, entry.data[CONF_COUNTRY]
            )
            if error is None:
                return self.async_update_reload_and_abort(
                    entry, data_updates={CONF_PASSWORD_HASH: password_hash}
                )
            errors["base"] = error

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=vol.Schema({vol.Required(CONF_PASSWORD): _PASSWORD}),
            description_placeholders={"username": entry.data[CONF_USERNAME]},
            errors=errors,
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        return MovaOptionsFlow()


class MovaOptionsFlow(OptionsFlow):
    """Polling interval, default feed portions and schedule write switch."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        if user_input is not None:
            user_input[CONF_SCAN_INTERVAL] = int(user_input[CONF_SCAN_INTERVAL])
            user_input[CONF_DEFAULT_PORTIONS] = int(user_input[CONF_DEFAULT_PORTIONS])
            return self.async_create_entry(data=user_input)

        options = self.config_entry.options
        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_SCAN_INTERVAL,
                        default=options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL),
                    ): NumberSelector(
                        NumberSelectorConfig(
                            min=MIN_SCAN_INTERVAL,
                            max=MAX_SCAN_INTERVAL,
                            step=1,
                            unit_of_measurement="s",
                            mode=NumberSelectorMode.BOX,
                        )
                    ),
                    vol.Required(
                        CONF_DEFAULT_PORTIONS,
                        default=options.get(CONF_DEFAULT_PORTIONS, DEFAULT_PORTIONS),
                    ): NumberSelector(
                        NumberSelectorConfig(
                            min=1, max=MAX_MANUAL_PORTIONS, step=1, mode=NumberSelectorMode.BOX
                        )
                    ),
                    vol.Required(
                        CONF_ENABLE_SCHEDULE_WRITE,
                        default=options.get(CONF_ENABLE_SCHEDULE_WRITE, False),
                    ): BooleanSelector(),
                }
            ),
        )
