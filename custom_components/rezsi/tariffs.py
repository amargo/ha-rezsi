"""Dated tariff blocks: load, look up by day, apply user overrides. No HA imports."""
from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import date
from pathlib import Path
from typing import Any

import yaml

TARIFF_FILE = Path(__file__).with_name("tariffs.yaml")


@dataclass(frozen=True)
class Electricity:
    reduced: float
    above: float
    band_kwh: float
    market: float
    feed_in: float
    rhd_base_extra: float
    rhd_kwh_extra: float


@dataclass(frozen=True)
class Gas:
    reduced: float
    above: float
    band_m3: float
    market: float


@dataclass(frozen=True)
class Tariff:
    valid_from: date
    source: str
    electricity: Electricity
    gas: Gas
    vat: float


def _as_date(v: Any) -> date:
    return v if isinstance(v, date) else date.fromisoformat(str(v))


def load_tariffs(path: Path = TARIFF_FILE) -> list[Tariff]:
    """Load blocks sorted by valid_from; each block inherits unset keys."""
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or []
    if not raw:
        raise ValueError(f"{path.name}: no tariff blocks")
    out: list[Tariff] = []
    elec: dict[str, Any] = {}
    gas: dict[str, Any] = {}
    vat: Any = None
    for block in sorted(raw, key=lambda b: _as_date(b["valid_from"])):
        day = _as_date(block["valid_from"])
        elec = {**elec, **(block.get("electricity") or {})}
        gas = {**gas, **(block.get("gas") or {})}
        vat = block.get("vat", vat)
        try:
            out.append(
                Tariff(
                    valid_from=day,
                    source=str(block["source"]).strip(),
                    electricity=Electricity(**{k: float(v) for k, v in elec.items()}),
                    gas=Gas(**{k: float(v) for k, v in gas.items()}),
                    vat=float(vat),
                )
            )
        except (TypeError, KeyError) as err:
            raise ValueError(f"incomplete tariff block {day.isoformat()}: {err}") from err
    return out


def tariff_for(tariffs: list[Tariff], day: date) -> Tariff:
    """Return the last block with valid_from <= day."""
    found = [t for t in tariffs if t.valid_from <= day]
    if not found:
        raise ValueError(f"no tariff valid on {day.isoformat()}")
    return found[-1]


def apply_overrides(t: Tariff, overrides: dict[str, Any]) -> Tariff:
    """Overrides look like {"electricity.market": 150}; None/"" mean 'use default'."""
    parts: dict[str, dict[str, float]] = {"electricity": {}, "gas": {}}
    for key, value in overrides.items():
        if value in (None, ""):
            continue
        group, _, field = key.partition(".")
        if group in parts and field:
            parts[group][field] = float(value)
    return replace(
        t,
        electricity=replace(t.electricity, **parts["electricity"]),
        gas=replace(t.gas, **parts["gas"]),
    )
