"""Schedule actions, registered as entity actions on the next_feed sensor.

Writing the schedule (3.6) is unverified: refused unless the
`enable_schedule_write` option is on (checked by the coordinator).
"""

from __future__ import annotations

from datetime import time
from typing import TYPE_CHECKING

import voluptuous as vol
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.entity_platform import EntityPlatform

from .const import DOMAIN, MAX_SCHEDULE_PORTIONS
from .models import ScheduleSlot, remove_slot, upsert_slot

if TYPE_CHECKING:
    from .sensor import MovaNextFeedSensor

SERVICE_SET_SCHEDULE = "set_schedule"
SERVICE_UPSERT_SLOT = "upsert_schedule_slot"
SERVICE_REMOVE_SLOT = "remove_schedule_slot"

_PORTIONS = vol.All(vol.Coerce(int), vol.Range(min=1, max=MAX_SCHEDULE_PORTIONS))
_SLOT = {
    vol.Required("time"): cv.time,
    vol.Required("portions"): _PORTIONS,
    vol.Optional("enabled", default=True): cv.boolean,
}


def _slot(data: dict) -> ScheduleSlot:
    when: time = data["time"]
    return ScheduleSlot(when.hour, when.minute, data["portions"], data["enabled"])


def _current(slots: tuple[ScheduleSlot, ...] | None) -> tuple[ScheduleSlot, ...]:
    if slots is None:
        raise HomeAssistantError(
            translation_domain=DOMAIN, translation_key="schedule_unknown"
        )
    return slots


async def _set_schedule(entity: MovaNextFeedSensor, call) -> None:
    slots = tuple(_slot(s) for s in call.data["slots"])
    await entity.coordinator.async_update_schedule(entity.did, lambda _old: slots)


async def _upsert_slot(entity: MovaNextFeedSensor, call) -> None:
    slot = _slot(call.data)
    await entity.coordinator.async_update_schedule(
        entity.did, lambda old: upsert_slot(_current(old), slot)
    )


async def _remove_slot(entity: MovaNextFeedSensor, call) -> None:
    when: time = call.data["time"]

    def change(old):
        try:
            return remove_slot(_current(old), when.hour, when.minute)
        except ValueError as err:
            raise ServiceValidationError(
                translation_domain=DOMAIN, translation_key="slot_not_found"
            ) from err

    await entity.coordinator.async_update_schedule(entity.did, change)


def async_register_schedule_services(platform: EntityPlatform) -> None:
    """Register the schedule entity actions on the sensor platform."""
    platform.async_register_entity_service(
        SERVICE_SET_SCHEDULE,
        {vol.Required("slots"): vol.All(cv.ensure_list, [vol.Schema(_SLOT)])},
        _set_schedule,
    )
    platform.async_register_entity_service(SERVICE_UPSERT_SLOT, _SLOT, _upsert_slot)
    platform.async_register_entity_service(
        SERVICE_REMOVE_SLOT, {vol.Required("time"): cv.time}, _remove_slot
    )
