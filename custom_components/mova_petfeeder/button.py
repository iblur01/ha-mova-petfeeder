"""Feed button and `feed` entity action for Mova feeders."""

from __future__ import annotations

import voluptuous as vol
from homeassistant.components.button import ButtonEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_platform
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import CONF_DEFAULT_PORTIONS, DEFAULT_PORTIONS, MAX_MANUAL_PORTIONS
from .coordinator import MovaConfigEntry
from .entity import MovaEntity

SERVICE_FEED = "feed"


async def async_setup_entry(
    hass: HomeAssistant, entry: MovaConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    coordinator = entry.runtime_data
    async_add_entities(
        MovaFeedButton(coordinator, state.device, "feed")
        for state in coordinator.data.values()
    )
    entity_platform.async_get_current_platform().async_register_entity_service(
        SERVICE_FEED,
        {
            vol.Optional("portions"): vol.All(
                vol.Coerce(int), vol.Range(min=1, max=MAX_MANUAL_PORTIONS)
            )
        },
        "async_feed",
    )


class MovaFeedButton(MovaEntity, ButtonEntity):
    _attr_translation_key = "feed"

    async def async_press(self) -> None:
        await self.async_feed()

    async def async_feed(self, portions: int | None = None) -> None:
        """Dispense `portions`, or the `default_portions` option."""
        if portions is None:
            portions = self.coordinator.config_entry.options.get(
                CONF_DEFAULT_PORTIONS, DEFAULT_PORTIONS
            )
        await self.coordinator.async_feed(self.did, int(portions))
