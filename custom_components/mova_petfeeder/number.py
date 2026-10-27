"""Portion size number for Mova feeders."""

from __future__ import annotations

from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import MAX_PORTION_SIZE, MIN_PORTION_SIZE, PROP_PORTION_SIZE
from .coordinator import MovaConfigEntry
from .entity import MovaEntity


async def async_setup_entry(
    hass: HomeAssistant, entry: MovaConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    coordinator = entry.runtime_data
    async_add_entities(
        MovaPortionNumber(coordinator, state.device, "portion_size")
        for state in coordinator.data.values()
    )


class MovaPortionNumber(MovaEntity, NumberEntity):
    """Property 3.4."""

    _attr_translation_key = "portion_size"
    _attr_entity_category = EntityCategory.CONFIG
    _attr_native_min_value = MIN_PORTION_SIZE
    _attr_native_max_value = MAX_PORTION_SIZE
    _attr_native_step = 1
    _attr_mode = NumberMode.BOX

    @property
    def native_value(self) -> int | None:
        return self.state_data.portion_size if self.state_data else None

    async def async_set_native_value(self, value: float) -> None:
        await self.coordinator.async_set_prop(
            self.did, PROP_PORTION_SIZE, "portion_size", int(value)
        )
