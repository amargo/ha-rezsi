"""Billing-period state per config entry."""
from __future__ import annotations

from datetime import date
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.storage import Store
from homeassistant.util import dt as dt_util

from .const import DOMAIN


class PeriodStore:
    """Period start and the last closed period, kept in .storage."""

    def __init__(self, hass: HomeAssistant, entry_id: str) -> None:
        self._store: Store[dict[str, Any]] = Store(hass, 1, f"{DOMAIN}.{entry_id}")
        self.period_start: date = dt_util.now().date()
        self.previous: dict[str, Any] | None = None

    async def async_load(self, default_start: date) -> None:
        data = await self._store.async_load() or {}
        start = data.get("period_start")
        self.period_start = date.fromisoformat(start) if start else default_start
        self.previous = data.get("previous")

    async def async_set_start(self, day: date) -> None:
        self.period_start = day
        await self._save()

    async def async_close_period(self, today: date, summary: dict[str, Any]) -> None:
        self.previous = {**summary, "idoszak_vege": today.isoformat()}
        self.period_start = today
        await self._save()

    async def async_remove(self) -> None:
        await self._store.async_remove()

    async def _save(self) -> None:
        await self._store.async_save(
            {"period_start": self.period_start.isoformat(), "previous": self.previous}
        )
