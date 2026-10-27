"""Mova Pet Feeder integration (MOVAhome cloud)."""

from __future__ import annotations

import logging

from homeassistant.const import CONF_PASSWORD, CONF_USERNAME, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import MovaClient
from .const import CONF_COUNTRY, CONF_PASSWORD_HASH
from .coordinator import MovaConfigEntry, MovaCoordinator
from .models import hash_password

_LOGGER = logging.getLogger(__name__)

PLATFORMS = [
    Platform.BINARY_SENSOR,
    Platform.BUTTON,
    Platform.NUMBER,
    Platform.SENSOR,
    Platform.SWITCH,
]

# v1 entities that no longer exist (unique_id suffixes).
OBSOLETE_SUFFIXES = ("_portion_size_sensor", "_manual_portions")


async def async_setup_entry(hass: HomeAssistant, entry: MovaConfigEntry) -> bool:
    """Set up Mova feeders from a config entry."""
    client = MovaClient(
        async_get_clientsession(hass),
        entry.data[CONF_USERNAME],
        entry.data[CONF_PASSWORD_HASH],
        entry.data[CONF_COUNTRY],
    )
    coordinator = MovaCoordinator(hass, entry, client)
    # Auth error -> reauth; connection/API error -> ConfigEntryNotReady.
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator
    entry.async_on_unload(coordinator.async_shutdown)
    entry.async_on_unload(entry.add_update_listener(_async_reload))

    remove_obsolete_entities(hass, entry)
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: MovaConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def _async_reload(hass: HomeAssistant, entry: MovaConfigEntry) -> None:
    await hass.config_entries.async_reload(entry.entry_id)


def remove_obsolete_entities(hass: HomeAssistant, entry: MovaConfigEntry) -> None:
    """Remove v1 entities replaced by the feed action or the number entity."""
    registry = er.async_get(hass)
    for reg in er.async_entries_for_config_entry(registry, entry.entry_id):
        if reg.unique_id.endswith(OBSOLETE_SUFFIXES):
            _LOGGER.debug("Removing obsolete entity %s", reg.entity_id)
            registry.async_remove(reg.entity_id)


async def async_migrate_entry(hass: HomeAssistant, entry: MovaConfigEntry) -> bool:
    """Migrate v1 (clear password) to v2 (password hash), without network."""
    if entry.version > 2:
        return False
    if entry.version == 1:
        data = dict(entry.data)
        password = data.pop(CONF_PASSWORD, None)
        if password is not None:
            data[CONF_PASSWORD_HASH] = hash_password(password)
        hass.config_entries.async_update_entry(
            entry,
            data=data,
            version=2,
            unique_id=entry.unique_id or data[CONF_USERNAME].lower(),
        )
        _LOGGER.debug("Migrated Mova config entry to version 2")
    return True
