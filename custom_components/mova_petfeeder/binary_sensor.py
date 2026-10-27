"""Connectivity binary sensor for Mova feeders."""

from __future__ import annotations

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .coordinator import MovaConfigEntry
from .entity import MovaEntity


async def async_setup_entry(
    hass: HomeAssistant, entry: MovaConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    coordinator = entry.runtime_data
    async_add_entities(
        MovaOnlineSensor(coordinator, state.device, "online")
        for state in coordinator.data.values()
    )


class MovaOnlineSensor(MovaEntity, BinarySensorEntity):
    """Online flag from listV2."""

    _attr_translation_key = "online"
    _attr_device_class = BinarySensorDeviceClass.CONNECTIVITY
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    @property
    def is_on(self) -> bool | None:
        return self.state_data.device.online if self.state_data else None
