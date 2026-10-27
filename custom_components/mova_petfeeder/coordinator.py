"""Polling coordinator and commands for Mova feeders."""

from __future__ import annotations

import asyncio
import logging
from collections import defaultdict
from collections.abc import Awaitable, Callable
from dataclasses import replace
from datetime import timedelta
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import CALLBACK_TYPE, HomeAssistant
from homeassistant.exceptions import (
    ConfigEntryAuthFailed,
    HomeAssistantError,
    ServiceValidationError,
)
from homeassistant.helpers.event import async_call_later
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import MovaAuthError, MovaClient, MovaError
from .const import (
    ALL_KEYS,
    CONF_ENABLE_SCHEDULE_WRITE,
    CONF_SCAN_INTERVAL,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    FAILURE_TOLERANCE,
    MAX_MANUAL_PORTIONS,
    MAX_SCHEDULE_PORTIONS,
    MAX_SCHEDULE_SLOTS,
    PROP_SCHEDULE,
    REFRESH_DELAY,
)
from .models import (
    FeederState,
    MovaDevice,
    ScheduleSlot,
    build_feed_params,
    build_set_props,
    build_state,
    encode_schedule,
)

_LOGGER = logging.getLogger(__name__)

type MovaConfigEntry = ConfigEntry[MovaCoordinator]


class MovaCoordinator(DataUpdateCoordinator[dict[str, FeederState]]):
    """Poll every feeder of the account; data is {did: FeederState}."""

    config_entry: MovaConfigEntry

    def __init__(
        self, hass: HomeAssistant, entry: MovaConfigEntry, client: MovaClient
    ) -> None:
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=DOMAIN,
            update_interval=timedelta(
                seconds=entry.options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
            ),
        )
        self.client = client
        self.failures = 0
        self.last_error: str | None = None
        self._known_dids: set[str] | None = None
        self._locks: defaultdict[str, asyncio.Lock] = defaultdict(asyncio.Lock)
        self._unsub_refresh: CALLBACK_TYPE | None = None

    async def _async_update_data(self) -> dict[str, FeederState]:
        try:
            data = await self._fetch()
        except MovaAuthError as err:
            self.last_error = type(err).__name__
            raise ConfigEntryAuthFailed(str(err)) from err
        except MovaError as err:
            self.failures += 1
            self.last_error = type(err).__name__
            if self.data is not None and self.failures < FAILURE_TOLERANCE:
                _LOGGER.warning(
                    "Mova poll failed (%s: %s), %d/%d, keeping previous data",
                    type(err).__name__,
                    err,
                    self.failures,
                    FAILURE_TOLERANCE,
                )
                return self.data
            raise UpdateFailed(f"{type(err).__name__}: {err}") from err
        except Exception as err:
            self.last_error = type(err).__name__
            _LOGGER.exception("Unexpected error while polling Mova")
            raise UpdateFailed(type(err).__name__) from err
        self.failures = 0
        self.last_error = None
        return data

    async def _fetch(self) -> dict[str, FeederState]:
        devices = await self.client.list_devices()
        dids = {d.did for d in devices}
        if self._known_dids is None:
            self._known_dids = dids
        elif dids - self._known_dids:
            _LOGGER.info("New Mova feeder found: reload the integration to add it")
            self._known_dids |= dids
        props = await asyncio.gather(
            *(self.client.get_props(d.did, ALL_KEYS) for d in devices)
        )
        return {d.did: build_state(d, p) for d, p in zip(devices, props, strict=True)}

    async def _async_command(
        self, did: str, call: Callable[[MovaDevice], Awaitable[None]]
    ) -> FeederState:
        """Run one command on a feeder: online check, per-feeder lock, error mapping."""
        state = (self.data or {}).get(did)
        if state is None:
            raise HomeAssistantError(
                translation_domain=DOMAIN, translation_key="unknown_feeder"
            )
        if not state.device.online:
            raise HomeAssistantError(translation_domain=DOMAIN, translation_key="offline")
        lock = self._locks[did]
        if lock.locked():
            raise HomeAssistantError(translation_domain=DOMAIN, translation_key="busy")
        async with lock:
            try:
                await call(state.device)
            except MovaAuthError as err:
                self.config_entry.async_start_reauth(self.hass)
                raise HomeAssistantError(
                    translation_domain=DOMAIN, translation_key="auth_failed"
                ) from err
            except MovaError as err:
                raise HomeAssistantError(
                    translation_domain=DOMAIN,
                    translation_key="command_failed",
                    translation_placeholders={"error": f"{type(err).__name__}: {err}"},
                ) from err
        self._schedule_refresh()
        return state

    def _schedule_refresh(self) -> None:
        """Refresh 10 s after a command; a pending refresh is replaced."""
        if self._unsub_refresh is not None:
            self._unsub_refresh()
        self._unsub_refresh = async_call_later(
            self.hass, REFRESH_DELAY, self._async_delayed_refresh
        )

    async def _async_delayed_refresh(self, _now: Any) -> None:
        self._unsub_refresh = None
        await self.async_request_refresh()

    async def async_shutdown(self) -> None:
        """Cancel the pending refresh and stop polling."""
        if self._unsub_refresh is not None:
            self._unsub_refresh()
            self._unsub_refresh = None
        await super().async_shutdown()

    def _set_optimistic(self, did: str, **changes: Any) -> None:
        state = self.data[did]
        self.async_set_updated_data({**self.data, did: replace(state, **changes)})

    async def async_feed(self, did: str, portions: int) -> None:
        """Dispense `portions` now."""
        if not 1 <= portions <= MAX_MANUAL_PORTIONS:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="invalid_portions",
                translation_placeholders={"max": str(MAX_MANUAL_PORTIONS)},
            )
        await self._async_command(
            did,
            lambda dev: self.client.action(dev, build_feed_params(dev.did, portions)),
        )

    async def async_set_prop(
        self, did: str, prop: tuple[int, int], field: str, value: Any
    ) -> None:
        """Write one property, then update `field` optimistically."""
        await self._async_command(
            did,
            lambda dev: self.client.set_properties(
                dev, build_set_props(dev.did, [(*prop, value)])
            ),
        )
        self._set_optimistic(did, **{field: value})

    async def async_update_schedule(
        self,
        did: str,
        change: Callable[[tuple[ScheduleSlot, ...] | None], tuple[ScheduleSlot, ...]],
    ) -> None:
        """Rewrite the whole schedule (3.6) from `change(current_slots)`."""
        if not self.config_entry.options.get(CONF_ENABLE_SCHEDULE_WRITE, False):
            raise ServiceValidationError(
                translation_domain=DOMAIN, translation_key="schedule_write_disabled"
            )
        state = (self.data or {}).get(did)
        slots = change(state.schedule if state else None)
        if len(slots) > MAX_SCHEDULE_SLOTS or any(
            not 1 <= s.portions <= MAX_SCHEDULE_PORTIONS for s in slots
        ):
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="invalid_schedule",
                translation_placeholders={
                    "slots": str(MAX_SCHEDULE_SLOTS),
                    "portions": str(MAX_SCHEDULE_PORTIONS),
                },
            )
        # ASSUMPTION: 3.6 is written back in the format it is read in.
        value = encode_schedule(slots)
        await self._async_command(
            did,
            lambda dev: self.client.set_properties(
                dev, build_set_props(dev.did, [(*PROP_SCHEDULE, value)])
            ),
        )
        self._set_optimistic(did, schedule=slots)
