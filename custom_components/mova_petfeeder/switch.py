"""MOVAhome feeder settings with confirmed mappings."""

from __future__ import annotations

from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import PROP_ANTI_GLUTTON, PROP_NIGHT_MODE
from .coordinator import MovaConfigEntry
from .entity import MovaEntity


async def async_setup_entry(
    hass: HomeAssistant, entry: MovaConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    coordinator = entry.runtime_data
    entities: list[MovaSwitch] = []
    for state in coordinator.data.values():
        entities += [
            MovaNightModeSwitch(coordinator, state.device, "night_mode"),
            MovaAntiGluttonSwitch(coordinator, state.device, "anti_glutton"),
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


class MovaNightModeSwitch(MovaSwitch):
    """Night light mode uses inverted values in MOVAhome (0 means enabled)."""

    _attr_translation_key = "night_mode"
    _prop = PROP_NIGHT_MODE
    _field = "night_mode"

    async def async_turn_on(self, **kwargs: Any) -> None:
        await self.coordinator.async_set_prop(
            self.did, self._prop, self._field, 0, optimistic_value=True
        )

    async def async_turn_off(self, **kwargs: Any) -> None:
        await self.coordinator.async_set_prop(
            self.did, self._prop, self._field, 1, optimistic_value=False
        )


class MovaAntiGluttonSwitch(MovaSwitch):
    """Anti-glutton mode switch (property 3.3)."""

    _attr_translation_key = "anti_glutton"
    _attr_entity_category = EntityCategory.CONFIG
    _prop = PROP_ANTI_GLUTTON
    _field = "anti_glutton"

    async def async_turn_on(self, **kwargs: Any) -> None:
        await self.coordinator.async_set_prop(
            self.did, self._prop, self._field, 1, optimistic_value=True
        )

    async def async_turn_off(self, **kwargs: Any) -> None:
        await self.coordinator.async_set_prop(
            self.did, self._prop, self._field, 0, optimistic_value=False
        )
