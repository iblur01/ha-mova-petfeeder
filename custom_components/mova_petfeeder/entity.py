"""Base entity for Mova feeders."""

from __future__ import annotations

from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import MovaCoordinator
from .models import FeederState, MovaDevice


def unique_id_prefix(device: MovaDevice) -> str:
    """Return the unique_id prefix: MAC without colons, or the did if no MAC."""
    return device.mac.replace(":", "").lower() if device.mac else device.did


class MovaEntity(CoordinatorEntity[MovaCoordinator]):
    """Entity bound to one feeder of the coordinator data."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: MovaCoordinator, device: MovaDevice, key: str) -> None:
        super().__init__(coordinator)
        self.did = device.did
        self._attr_unique_id = f"{unique_id_prefix(device)}_{key}"
        self._attr_device_info = DeviceInfo(
            # Identifier kept from v1 (MAC) so the device is not recreated.
            identifiers={(DOMAIN, device.mac or device.did)},
            connections={(dr.CONNECTION_NETWORK_MAC, device.mac)} if device.mac else set(),
            manufacturer="Mova",
            model=device.model,
            name=device.name,
            sw_version=device.firmware,
        )

    @property
    def state_data(self) -> FeederState | None:
        """Return the latest snapshot of this feeder."""
        return (self.coordinator.data or {}).get(self.did)

    @property
    def available(self) -> bool:
        return super().available and self.state_data is not None
