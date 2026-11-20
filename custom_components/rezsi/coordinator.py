"""Hourly recomputation for one meter site."""
from __future__ import annotations

import logging
from datetime import date, timedelta
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .calc import CalcOptions, DayUsage, Result, compute
from .const import (
    CONF_ELEC_MULT, CONF_EXPORT, CONF_GAS, CONF_GAS_MULT, CONF_IMPORT, CONF_OVERRIDES, CONF_RHD, CONF_SZALDO,
)
from .statistics import async_daily_changes
from .store import PeriodStore
from .tariffs import Tariff, apply_overrides, tariff_for

_LOGGER = logging.getLogger(__name__)


class RezsiCoordinator(DataUpdateCoordinator[Result]):
    """Fetch daily statistics since the period start and compute costs."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry, store: PeriodStore, tariffs: list[Tariff]) -> None:
        super().__init__(hass, _LOGGER, config_entry=entry, name=entry.title, update_interval=timedelta(hours=1))
        self.store = store
        self.tariffs = tariffs
        self.gas_ok = False
        self.first_day: date | None = None

    @property
    def cfg(self) -> dict[str, Any]:
        return {**self.config_entry.data, **self.config_entry.options}

    @property
    def has_gas(self) -> bool:
        return bool(self.cfg.get(CONF_GAS))

    async def _async_update_data(self) -> Result:
        cfg = self.cfg
        start = self.store.period_start
        today = dt_util.now().date()
        ids = {"imp": cfg.get(CONF_IMPORT), "exp": cfg.get(CONF_EXPORT), "gas": cfg.get(CONF_GAS)}
        changes = await async_daily_changes(self.hass, ids, start, today)
        imp = changes.get("imp") or {}
        if not imp:
            raise UpdateFailed(f"no statistics for {cfg.get(CONF_IMPORT)}")
        exp = changes.get("exp") or {}
        gas = changes.get("gas") or {}
        self.gas_ok = bool(gas)
        self.first_day = min(imp)
        usage = [
            DayUsage(d, imp.get(d, 0.0), exp.get(d, 0.0), gas.get(d, 0.0))
            for d in (start + timedelta(days=n) for n in range((today - start).days + 1))
        ]
        overrides = cfg.get(CONF_OVERRIDES) or {}
        opts = CalcOptions(
            szaldo=bool(cfg.get(CONF_SZALDO, True)),
            elec_band_mult=float(cfg.get(CONF_ELEC_MULT, 1)),
            gas_band_mult=float(cfg.get(CONF_GAS_MULT, 1)),
            rhd=bool(cfg.get(CONF_RHD, False)),
        )
        try:
            return compute(usage, lambda d: apply_overrides(tariff_for(self.tariffs, d), overrides), opts)
        except ValueError as err:
            raise UpdateFailed(str(err)) from err

    def totals(self) -> tuple[float, float]:
        """(regulated, market) for electricity plus gas when available."""
        r = self.data
        gas = self.has_gas and self.gas_ok
        return (r.elec_reg + (r.gas_reg if gas else 0.0), r.elec_mkt + (r.gas_mkt if gas else 0.0))

    def summary(self) -> dict[str, Any]:
        """Snapshot stored when the period is closed."""
        r = self.data
        reg, mkt = self.totals()
        return {
            "idoszak_kezdete": self.store.period_start.isoformat(),
            "eltelt_napok": r.days,
            "villany_rezsiaron": round(r.elec_reg),
            "villany_piaci_aron": round(r.elec_mkt),
            "gaz_rezsiaron": round(r.gas_reg) if self.gas_ok else None,
            "gaz_piaci_aron": round(r.gas_mkt) if self.gas_ok else None,
            "osszesen_rezsiaron": round(reg),
            "osszesen_piaci_aron": round(mkt),
            "elszamolt_kwh": round(r.billed_kwh, 1),
            "gaz_m3": round(r.gas_m3, 1),
        }

    def attributes(self) -> dict[str, Any]:
        r = self.data
        return {
            "idoszak_kezdete": self.store.period_start.isoformat(),
            "eltelt_napok": r.days,
            "vetel_kwh": round(r.imp_kwh, 1),
            "betaplalas_kwh": round(r.exp_kwh, 1),
            "elszamolt_kwh": round(r.billed_kwh, 1),
            "gaz_m3": round(r.gas_m3, 1),
            "savhatar_aranyos": round(r.band_kwh, 1),
            "savhatar_felhasznalt_pct": round(r.band_used_pct, 1),
            "gaz_savhatar_aranyos": round(r.gas_band_m3, 1),
            "tarifa_valid_from": r.tariff.valid_from.isoformat(),
            "tarifa_forras": r.tariff.source,
            "havi_bontas": r.monthly,
            "elozo_idoszak": self.store.previous,
            "adat_hianyos": bool(self.first_day and self.first_day > self.store.period_start),
            "elso_adat_napja": self.first_day.isoformat() if self.first_day else None,
        }
