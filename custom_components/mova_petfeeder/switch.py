from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    data = hass.data[DOMAIN][entry.entry_id]
    coordinator = data["coordinator"]
    feeders = data["feeders"]
    entities = []
    for feeder in feeders:
        entities += [
            MovaScheduleSwitch(coordinator, feeder),
            MovaSoundSwitch(coordinator, feeder),
        ]
    async_add_entities(entities)


class _MovaBaseSwitch(CoordinatorEntity, SwitchEntity):
    _attr_has_entity_name = True

    def __init__(self, coordinator, feeder) -> None:
        super().__init__(coordinator)
        self._feeder = feeder

    @property
    def device_info(self) -> DeviceInfo:
        return DeviceInfo(
            identifiers={(DOMAIN, self._feeder.mac)},
            name=self._feeder.name,
            model=self._feeder.model,
            manufacturer="Mova",
        )

    @property
    def available(self) -> bool:
        return self._feeder.available


class MovaScheduleSwitch(_MovaBaseSwitch):
    _attr_icon = "mdi:calendar-clock"
    _attr_name = "Schedule"

    def __init__(self, coordinator, feeder) -> None:
        super().__init__(coordinator, feeder)
        self._attr_unique_id = f"{feeder.unique_id_prefix}_schedule"

    @property
    def is_on(self) -> bool:
        return self._feeder.schedule_enabled

    async def async_turn_on(self, **kwargs) -> None:
        await self.hass.async_add_executor_job(self._feeder.set_schedule_enabled, True)
        await self.coordinator.async_request_refresh()

    async def async_turn_off(self, **kwargs) -> None:
        await self.hass.async_add_executor_job(self._feeder.set_schedule_enabled, False)
        await self.coordinator.async_request_refresh()


class MovaSoundSwitch(_MovaBaseSwitch):
    _attr_icon = "mdi:volume-high"
    _attr_name = "Sound"

    def __init__(self, coordinator, feeder) -> None:
        super().__init__(coordinator, feeder)
        self._attr_unique_id = f"{feeder.unique_id_prefix}_sound"

    @property
    def is_on(self) -> bool:
        return self._feeder.sound_enabled

    async def async_turn_on(self, **kwargs) -> None:
        await self.hass.async_add_executor_job(self._feeder.set_sound_enabled, True)
        await self.coordinator.async_request_refresh()

    async def async_turn_off(self, **kwargs) -> None:
        await self.hass.async_add_executor_job(self._feeder.set_sound_enabled, False)
        await self.coordinator.async_request_refresh()
