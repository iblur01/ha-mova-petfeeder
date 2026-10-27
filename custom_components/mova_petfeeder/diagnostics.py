"""Diagnostics for Mova Pet Feeder (identifiers and secrets redacted)."""

from __future__ import annotations

from dataclasses import asdict
from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant

from .const import CONF_PASSWORD_HASH
from .coordinator import MovaConfigEntry

TO_REDACT = {
    CONF_PASSWORD,
    CONF_PASSWORD_HASH,
    CONF_USERNAME,
    "access_token",
    "refresh_token",
    "uid",
    "did",
    "mac",
    "bindDomain",
    "bind_domain",
    "sn",
    "property",
    "masterUid",
}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: MovaConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    coordinator = entry.runtime_data
    payload = {
        "entry": {
            "title": "**REDACTED**",
            "version": entry.version,
            "data": dict(entry.data),
            "options": dict(entry.options),
        },
        "coordinator": {
            "last_update_success": coordinator.last_update_success,
            "consecutive_failures": coordinator.failures,
            "last_error": coordinator.last_error,
            "token_expires_in": coordinator.client.token_expires_in,
        },
        # A list, not a dict keyed by did, so the did never leaks as a key.
        "feeders": [asdict(state) for state in (coordinator.data or {}).values()],
    }
    return async_redact_data(payload, TO_REDACT)
