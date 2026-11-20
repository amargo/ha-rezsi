"""Editable billing-period start."""
from __future__ import annotations

from datetime import date

from homeassistant.components.date import DateEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import RezsiConfigEntry
from .entity import RezsiEntity


async def async_setup_entry(hass: HomeAssistant, entry: RezsiConfigEntry, add: AddEntitiesCallback) -> None:
    add([PeriodStartDate(entry.runtime_data, "idoszak_kezdete", "Időszak kezdete")])


class PeriodStartDate(RezsiEntity, DateEntity):
    _attr_icon = "mdi:calendar-start"

    @property
    def native_value(self) -> date:
        return self.coordinator.store.period_start

    async def async_set_value(self, value: date) -> None:
        await self.coordinator.store.async_set_start(value)
        await self.coordinator.async_refresh()
