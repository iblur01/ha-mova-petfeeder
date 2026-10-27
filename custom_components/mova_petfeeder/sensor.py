"""Sensors for Mova feeders: food level and next scheduled feeding."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.const import UnitOfMass
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_platform
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util import dt as dt_util

from .coordinator import MovaConfigEntry
from .entity import MovaEntity
from .models import next_feed
from .services import async_register_schedule_services


async def async_setup_entry(
    hass: HomeAssistant, entry: MovaConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    coordinator = entry.runtime_data
    entities: list[SensorEntity] = []
    for state in coordinator.data.values():
        entities += [
            MovaFoodLevelSensor(coordinator, state.device, "food_level"),
            # unique_id kept from v1 ("schedule_sensor"), now a timestamp.
            MovaNextFeedSensor(coordinator, state.device, "schedule_sensor"),
        ]
    async_add_entities(entities)
    async_register_schedule_services(entity_platform.async_get_current_platform())


class MovaFoodLevelSensor(MovaEntity, SensorEntity):
    _attr_translation_key = "food_level"
    _attr_device_class = SensorDeviceClass.WEIGHT
    _attr_native_unit_of_measurement = UnitOfMass.GRAMS
    _attr_state_class = SensorStateClass.MEASUREMENT

    @property
    def native_value(self) -> int | None:
        return self.state_data.food_level_g if self.state_data else None


class MovaNextFeedSensor(MovaEntity, SensorEntity):
    """Next feeding; carries the schedule actions."""

    _attr_translation_key = "next_feed"
    _attr_device_class = SensorDeviceClass.TIMESTAMP

    @property
    def native_value(self) -> datetime | None:
        state = self.state_data
        if state is None:
            return None
        # Slot times are device-local; assumed to match the HA time zone.
        return next_feed(state.schedule, dt_util.now())

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        state = self.state_data
        if state is None or state.schedule is None:
            return {"slots": None}
        return {
            "slots": [
                {
                    "time": s.time,
                    "portions": s.portions,
                    "enabled": s.enabled,
                    "days_raw": s.days_raw,
                }
                for s in state.schedule
            ]
        }
