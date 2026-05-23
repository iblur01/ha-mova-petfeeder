from homeassistant.components.sensor import SensorEntity
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
            MovaFeedingsTodaySensor(coordinator, feeder),
            MovaPortionSizeSensor(coordinator, feeder),
        ]
    async_add_entities(entities)


class _MovaBaseSensor(CoordinatorEntity, SensorEntity):
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


class MovaFeedingsTodaySensor(_MovaBaseSensor):
    _attr_icon = "mdi:counter"
    _attr_name = "Feedings today"
    _attr_native_unit_of_measurement = "feedings"

    def __init__(self, coordinator, feeder) -> None:
        super().__init__(coordinator, feeder)
        self._attr_unique_id = f"{feeder.unique_id_prefix}_feedings_today"

    @property
    def native_value(self):
        return self._feeder.feedings_today


class MovaPortionSizeSensor(_MovaBaseSensor):
    _attr_icon = "mdi:bowl"
    _attr_name = "Portion size"
    _attr_native_unit_of_measurement = "portions"

    def __init__(self, coordinator, feeder) -> None:
        super().__init__(coordinator, feeder)
        self._attr_unique_id = f"{feeder.unique_id_prefix}_portion_size_sensor"

    @property
    def native_value(self):
        return self._feeder.portion_size
