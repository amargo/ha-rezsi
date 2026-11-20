"""Shared base entity: one device per meter site."""
from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import RezsiCoordinator


class RezsiEntity(CoordinatorEntity[RezsiCoordinator]):
    _attr_has_entity_name = True

    def __init__(self, coordinator: RezsiCoordinator, key: str, name: str) -> None:
        super().__init__(coordinator)
        entry = coordinator.config_entry
        self._attr_unique_id = f"{entry.entry_id}_{key}"
        self._attr_name = name
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=entry.title,
            manufacturer="Rezsi kalkulátor",
            entry_type=DeviceEntryType.SERVICE,
        )
