from homeassistant.components.sensor import SensorEntity, SensorStateClass
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
            MovaFoodLevelSensor(coordinator, feeder),
            MovaScheduleSensor(coordinator, feeder),
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


class MovaFoodLevelSensor(_MovaBaseSensor):
    _attr_icon = "mdi:food-drumstick"
    _attr_name = "Food level"
    _attr_native_unit_of_measurement = "%"
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, coordinator, feeder) -> None:
        super().__init__(coordinator, feeder)
        self._attr_unique_id = f"{feeder.unique_id_prefix}_food_level"

    @property
    def native_value(self):
        return self._feeder.food_level


class MovaScheduleSensor(_MovaBaseSensor):
    _attr_icon = "mdi:calendar-clock"
    _attr_name = "Schedule"

    def __init__(self, coordinator, feeder) -> None:
        super().__init__(coordinator, feeder)
        self._attr_unique_id = f"{feeder.unique_id_prefix}_schedule_sensor"

    @property
    def native_value(self) -> str:
        entries = self._feeder.schedule_entries
        if not entries:
            return "No schedule"
        active = [e for e in entries if e["enabled"]]
        return f"{len(active)}/{len(entries)} active"

    @property
    def extra_state_attributes(self) -> dict:
        return {
            f"slot_{i+1}": f"{e['time']} × {e['portions']} {'✓' if e['enabled'] else '✗'}"
            for i, e in enumerate(self._feeder.schedule_entries)
        }
