"""Connectivity binary sensor for Mova feeders."""

from __future__ import annotations

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .coordinator import MovaConfigEntry, MovaCoordinator
from .entity import MovaEntity
from .models import MovaDevice, PropValue


async def async_setup_entry(
    hass: HomeAssistant, entry: MovaConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    coordinator = entry.runtime_data
    async_add_entities(
        entity
        for state in coordinator.data.values()
        for entity in (
            MovaOnlineSensor(coordinator, state.device, "online"),
            MovaFaultFlagSensor(coordinator, state.device, "device_error", 0x01),
            MovaFaultFlagSensor(coordinator, state.device, "outlet_blocked", 0x02),
            MovaFaultFlagSensor(coordinator, state.device, "food_empty", 0x04),
            MovaFaultFlagSensor(coordinator, state.device, "low_battery", 0x08),
            MovaFaultFlagSensor(coordinator, state.device, "calibration_needed", 0x10),
        )
    )


class MovaOnlineSensor(MovaEntity, BinarySensorEntity):
    """Online flag from listV2."""

    _attr_translation_key = "online"
    _attr_device_class = BinarySensorDeviceClass.CONNECTIVITY
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    @property
    def is_on(self) -> bool | None:
        return self.state_data.device.online if self.state_data else None


class MovaFaultFlagSensor(MovaEntity, BinarySensorEntity):
    """One bit of the app's faultCodeMask (property 2.2)."""

    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(
        self, coordinator: MovaCoordinator, device: MovaDevice, key: str, mask: int
    ) -> None:
        super().__init__(coordinator, device, key)
        self._mask = mask
        self._attr_translation_key = key

    @property
    def is_on(self) -> bool | None:
        state = self.state_data
        entry: PropValue | None = state.raw.get("2.2") if state else None
        if entry is None or entry.value is None:
            return None
        try:
            return bool(int(entry.value) & self._mask)
        except ValueError:
            return None
