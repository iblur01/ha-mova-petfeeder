from homeassistant.components.button import ButtonEntity
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
    async_add_entities([MovaFeedButton(coordinator, feeder) for feeder in feeders])


class MovaFeedButton(CoordinatorEntity, ButtonEntity):
    _attr_icon = "mdi:food-variant"
    _attr_has_entity_name = True
    _attr_name = "Feed now"

    def __init__(self, coordinator, feeder) -> None:
        super().__init__(coordinator)
        self._feeder = feeder
        self._attr_unique_id = f"{feeder.unique_id_prefix}_feed"

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

    async def async_press(self) -> None:
        await self.hass.async_add_executor_job(self._feeder.feed)
        await self.coordinator.async_request_refresh()
