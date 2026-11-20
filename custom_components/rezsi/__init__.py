"""Rezsi kalkulátor: regulated vs market utility cost from HA statistics."""
from __future__ import annotations

import datetime as dt

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryError
from homeassistant.util import dt as dt_util

from .const import CONF_OVERRIDES, CONF_PERIOD_START
from .coordinator import RezsiCoordinator
from .store import PeriodStore
from .tariffs import apply_overrides, load_tariffs

PLATFORMS = [Platform.SENSOR, Platform.BUTTON, Platform.DATE]

type RezsiConfigEntry = ConfigEntry[RezsiCoordinator]


async def async_setup_entry(hass: HomeAssistant, entry: RezsiConfigEntry) -> bool:
    tariffs = await hass.async_add_executor_job(load_tariffs)
    overrides = {**entry.data, **entry.options}.get(CONF_OVERRIDES) or {}
    try:
        tariffs = [apply_overrides(t, overrides) for t in tariffs]
    except ValueError as err:
        raise ConfigEntryError(str(err)) from err
    store = PeriodStore(hass, entry.entry_id)
    start = entry.data.get(CONF_PERIOD_START)
    # Not `from datetime import date`: loading the date platform binds the package
    # attribute `date` to the submodule and would shadow it.
    default = dt.date.fromisoformat(start) if start else dt_util.now().date() - dt.timedelta(days=364)
    await store.async_load(default)
    coordinator = RezsiCoordinator(hass, entry, store, tariffs)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(_async_reload))
    return True


async def async_unload_entry(hass: HomeAssistant, entry: RezsiConfigEntry) -> bool:
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def async_remove_entry(hass: HomeAssistant, entry: RezsiConfigEntry) -> None:
    await PeriodStore(hass, entry.entry_id).async_remove()


async def _async_reload(hass: HomeAssistant, entry: RezsiConfigEntry) -> None:
    await hass.config_entries.async_reload(entry.entry_id)
