from homeassistant.components.number import NumberEntity, NumberMode
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
        entities += [MovaPortionNumber(coordinator, feeder), MovaManualPortionsNumber(coordinator, feeder)]
    async_add_entities(entities)


class MovaPortionNumber(CoordinatorEntity, NumberEntity):
    _attr_has_entity_name = True
    _attr_name = "Portion size"
    _attr_icon = "mdi:bowl-mix"
    _attr_native_min_value = 1
    _attr_native_max_value = 50
    _attr_native_step = 1
    _attr_mode = NumberMode.BOX
    _attr_native_unit_of_measurement = "portions"

    def __init__(self, coordinator, feeder) -> None:
        super().__init__(coordinator)
        self._feeder = feeder
        self._attr_unique_id = f"{feeder.unique_id_prefix}_portion_size"

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

    @property
    def native_value(self) -> int:
        return self._feeder.portion_size

    async def async_set_native_value(self, value: float) -> None:
        await self.hass.async_add_executor_job(self._feeder.set_portion_size, int(value))
        await self.coordinator.async_request_refresh()


class MovaManualPortionsNumber(CoordinatorEntity, NumberEntity):
    _attr_has_entity_name = True
    _attr_name = "Manual feed portions"
    _attr_icon = "mdi:food"
    _attr_native_min_value = 1
    _attr_native_max_value = 10
    _attr_native_step = 1
    _attr_mode = NumberMode.BOX
    _attr_native_unit_of_measurement = "portions"

    def __init__(self, coordinator, feeder) -> None:
        super().__init__(coordinator)
        self._feeder = feeder
        self._attr_unique_id = f"{feeder.unique_id_prefix}_manual_portions"

    @property
    def device_info(self):
        from homeassistant.helpers.entity import DeviceInfo
        return DeviceInfo(
            identifiers={(DOMAIN, self._feeder.mac)},
            name=self._feeder.name,
            model=self._feeder.model,
            manufacturer="Mova",
        )

    @property
    def available(self) -> bool:
        return self._feeder.available

    @property
    def native_value(self) -> int:
        return self._feeder.manual_portions

    async def async_set_native_value(self, value: float) -> None:
        self._feeder.set_manual_portions(int(value))
        self.async_write_ha_state()
