import logging
from datetime import timedelta

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import MovaCloudAPI, MovaFeeder
from .const import CONF_COUNTRY, DOMAIN, PLATFORMS, SCAN_INTERVAL

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    api = MovaCloudAPI(
        entry.data[CONF_USERNAME],
        entry.data[CONF_PASSWORD],
        entry.data[CONF_COUNTRY],
    )

    logged_in = await hass.async_add_executor_job(api.login)
    if not logged_in:
        return False

    raw_devices = await hass.async_add_executor_job(api.get_feeders)
    feeders = [MovaFeeder(api, d) for d in raw_devices]

    if not feeders:
        _LOGGER.error("No Mova feeders found on account")
        return False

    async def async_update():
        try:
            for feeder in feeders:
                await hass.async_add_executor_job(feeder.update)
        except Exception as exc:
            raise UpdateFailed(exc) from exc
        return feeders

    coordinator = DataUpdateCoordinator(
        hass,
        _LOGGER,
        name=DOMAIN,
        update_method=async_update,
        update_interval=timedelta(seconds=SCAN_INTERVAL),
    )

    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = {
        "coordinator": coordinator,
        "feeders": feeders,
        "api": api,
    }

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unloaded:
        hass.data[DOMAIN].pop(entry.entry_id)
    return unloaded
