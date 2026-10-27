"""Switches for Mova feeders: schedule and sound."""

from __future__ import annotations

from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import PROP_SCHEDULE_ON, PROP_SOUND_ON
from .coordinator import MovaConfigEntry
from .entity import MovaEntity


async def async_setup_entry(
    hass: HomeAssistant, entry: MovaConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    coordinator = entry.runtime_data
    entities: list[MovaSwitch] = []
    for state in coordinator.data.values():
        entities += [
            MovaScheduleSwitch(coordinator, state.device, "schedule"),
            MovaSoundSwitch(coordinator, state.device, "sound"),
        ]
    async_add_entities(entities)


class MovaSwitch(MovaEntity, SwitchEntity):
    """Switch backed by one boolean property."""

    _prop: tuple[int, int]
    _field: str

    @property
    def is_on(self) -> bool | None:
        return getattr(self.state_data, self._field) if self.state_data else None

    async def async_turn_on(self, **kwargs: Any) -> None:
        await self.coordinator.async_set_prop(self.did, self._prop, self._field, True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        await self.coordinator.async_set_prop(self.did, self._prop, self._field, False)


class MovaScheduleSwitch(MovaSwitch):
    """Property 3.2, exposed as is. Meaning NOT confirmed (0 with active slots); next_feed ignores it."""

    _attr_translation_key = "schedule_enabled"
    _prop = PROP_SCHEDULE_ON
    _field = "schedule_enabled"


class MovaSoundSwitch(MovaSwitch):
    _attr_translation_key = "sound"
    _attr_entity_category = EntityCategory.CONFIG
    _prop = PROP_SOUND_ON
    _field = "sound_enabled"
