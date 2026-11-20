"""'Leolvasás most' button: close the period and start a new one today."""
from __future__ import annotations

from homeassistant.components.button import ButtonEntity
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util import dt as dt_util

from . import RezsiConfigEntry
from .entity import RezsiEntity


async def async_setup_entry(hass: HomeAssistant, entry: RezsiConfigEntry, add: AddEntitiesCallback) -> None:
    add([ReadingButton(entry.runtime_data, "leolvasas_most", "Leolvasás most")])


class ReadingButton(RezsiEntity, ButtonEntity):
    _attr_icon = "mdi:counter"

    async def async_press(self) -> None:
        c = self.coordinator
        await c.async_refresh()  # close with up-to-date numbers
        if not c.last_update_success:
            raise HomeAssistantError("Nem sikerült frissíteni az adatokat, az időszak nincs lezárva")
        await c.store.async_close_period(dt_util.now().date(), c.summary())
        await c.async_refresh()
