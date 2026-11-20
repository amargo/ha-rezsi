"""Pure cost calculation, ported from the web Rezsikalkulátor calc(). No HA imports."""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field, replace
from datetime import date
from typing import Callable

from .tariffs import Tariff


@dataclass(frozen=True)
class DayUsage:
    day: date
    imp: float = 0.0
    exp: float = 0.0
    gas: float = 0.0


@dataclass(frozen=True)
class CalcOptions:
    szaldo: bool = True
    elec_band_mult: float = 1.0
    gas_band_mult: float = 1.0
    rhd: bool = False


@dataclass
class Result:
    days: int
    imp_kwh: float
    exp_kwh: float
    billed_kwh: float
    band_kwh: float
    band_used_pct: float  # billed kWh of the whole period / summed band, in percent
    credit: float
    elec_reg: float
    elec_mkt: float
    rhd: float
    gas_m3: float
    gas_band_m3: float
    gas_reg: float
    gas_mkt: float
    tariff: Tariff
    monthly: dict[str, dict[str, float]] = field(default_factory=dict)


def tier(q: float, cap: float, lo: float, hi: float) -> float:
    """Banded price: up to cap at lo, above at hi."""
    return min(q, cap) * lo + max(0.0, q - cap) * hi


def compute(usage: list[DayUsage], tariff_for: Callable[[date], Tariff], opts: CalcOptions) -> Result:
    """Cost of the period covered by `usage` (one entry per day).

    Szaldó nets import and export over the whole period. Days are grouped by the
    tariff block valid on them; each group gets the band in proportion to its day
    count and the billed quantity in proportion to its import (or days if no import).
    Negative daily deltas (meter reset, statistics glitch) are clamped to 0.
    """
    if not usage:
        raise ValueError("no usage data")
    usage = [replace(u, imp=max(0.0, u.imp), exp=max(0.0, u.exp), gas=max(0.0, u.gas)) for u in usage]
    groups: dict[date, list[DayUsage]] = defaultdict(list)
    blocks: dict[date, Tariff] = {}
    for u in usage:
        t = tariff_for(u.day)
        groups[t.valid_from].append(u)
        blocks[t.valid_from] = t

    n = len(usage)
    imp = sum(u.imp for u in usage)
    exp = sum(u.exp for u in usage)
    billed = max(0.0, imp - exp) if opts.szaldo else imp
    surplus = max(0.0, exp - imp) if opts.szaldo else exp

    band = credit = elec_reg = elec_mkt = rhd = 0.0
    gas_q = gas_band = gas_reg = gas_mkt = 0.0
    for key in sorted(groups):
        t, days = blocks[key], groups[key]
        d = len(days)
        e = t.electricity
        g_imp = sum(u.imp for u in days)
        g_exp = sum(u.exp for u in days)
        q = billed * (g_imp / imp if imp else d / n)
        b = e.band_kwh * opts.elec_band_mult * d / 365
        cr = surplus * (g_exp / exp if exp else d / n) * e.feed_in
        r = (e.rhd_base_extra * d / 365 + e.rhd_kwh_extra * q) * (1 + t.vat / 100) if opts.rhd else 0.0
        band += b
        credit += cr
        rhd += r
        elec_reg += tier(q, b, e.reduced, e.above) - cr
        elec_mkt += q * e.market - cr + r

        gq = sum(u.gas for u in days)
        gb = t.gas.band_m3 * opts.gas_band_mult * d / 365
        gas_q += gq
        gas_band += gb
        gas_reg += tier(gq, gb, t.gas.reduced, t.gas.above)
        gas_mkt += gq * t.gas.market

    monthly: dict[str, dict[str, float]] = {}
    for u in usage:
        m = monthly.setdefault(u.day.strftime("%Y-%m"), {"vetel_kwh": 0.0, "betaplalas_kwh": 0.0, "gaz_m3": 0.0})
        m["vetel_kwh"] += u.imp
        m["betaplalas_kwh"] += u.exp
        m["gaz_m3"] += u.gas
    monthly = {k: {kk: round(vv, 3) for kk, vv in v.items()} for k, v in monthly.items()}

    return Result(
        days=n,
        imp_kwh=imp,
        exp_kwh=exp,
        billed_kwh=billed,
        band_kwh=band,
        band_used_pct=billed / band * 100 if band else 0.0,
        credit=credit,
        elec_reg=elec_reg,
        elec_mkt=elec_mkt,
        rhd=rhd,
        gas_m3=gas_q,
        gas_band_m3=gas_band,
        gas_reg=gas_reg,
        gas_mkt=gas_mkt,
        tariff=blocks[max(blocks)],
        monthly=monthly,
    )
