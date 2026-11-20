"""Cost sensors for one meter site."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import RezsiConfigEntry
from .coordinator import RezsiCoordinator
from .entity import RezsiEntity


@dataclass(frozen=True)
class Desc:
    key: str
    name: str
    value: Callable[[RezsiCoordinator], float]
    gas: bool = False


def _diff(c: RezsiCoordinator) -> float:
    reg, mkt = c.totals()
    return mkt - reg


DESCS = (
    Desc("villany_rezsiaron", "Villany rezsiáron", lambda c: c.data.elec_reg),
    Desc("villany_piaci_aron", "Villany piaci áron", lambda c: c.data.elec_mkt),
    Desc("gaz_rezsiaron", "Gáz rezsiáron", lambda c: c.data.gas_reg, gas=True),
    Desc("gaz_piaci_aron", "Gáz piaci áron", lambda c: c.data.gas_mkt, gas=True),
    Desc("osszesen_rezsiaron", "Összesen rezsiáron", lambda c: c.totals()[0]),
    Desc("osszesen_piaci_aron", "Összesen piaci áron", lambda c: c.totals()[1]),
    Desc("kulonbseg", "Különbség", _diff),
    Desc("eves_becsles_piaci", "Éves becslés piaci", lambda c: c.totals()[1] * 365 / max(c.data.days, 1)),
)


async def async_setup_entry(hass: HomeAssistant, entry: RezsiConfigEntry, add: AddEntitiesCallback) -> None:
    c = entry.runtime_data
    add(RezsiSensor(c, d) for d in DESCS if not d.gas or c.has_gas)


class RezsiSensor(RezsiEntity, SensorEntity):
    _attr_device_class = SensorDeviceClass.MONETARY
    _attr_native_unit_of_measurement = "Ft"
    _attr_suggested_display_precision = 0

    def __init__(self, coordinator: RezsiCoordinator, desc: Desc) -> None:
        super().__init__(coordinator, desc.key, desc.name)
        self._desc = desc

    @property
    def available(self) -> bool:
        return super().available and (not self._desc.gas or self.coordinator.gas_ok)

    @property
    def native_value(self) -> float:
        return round(self._desc.value(self.coordinator), 2)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        attrs = self.coordinator.attributes()
        if self._desc.key == "kulonbseg":
            reg, _ = self.coordinator.totals()
            attrs["kulonbseg_pct"] = round(_diff(self.coordinator) / reg * 100, 1) if reg else None
        return attrs
