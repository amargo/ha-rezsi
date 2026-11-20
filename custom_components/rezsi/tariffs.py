"""Dated tariff blocks: load, look up by day, apply user overrides. No HA imports."""
from __future__ import annotations

from dataclasses import dataclass, fields, replace
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


_GROUPS = {"electricity": Electricity, "gas": Gas}
_BLOCK_KEYS = {"valid_from", "source", "electricity", "gas", "vat"}


def _as_date(v: Any) -> date:
    return v if isinstance(v, date) else date.fromisoformat(str(v))


def _floats(values: dict[str, Any], group: str, day: date) -> dict[str, float]:
    allowed = {f.name for f in fields(_GROUPS[group])}
    out: dict[str, float] = {}
    for key, value in values.items():
        if key not in allowed:
            raise ValueError(f"tariff block {day.isoformat()}: unknown key {group}.{key}")
        try:
            out[key] = float(value)
        except (TypeError, ValueError) as err:
            raise ValueError(
                f"tariff block {day.isoformat()}: {group}.{key} not a number: {value!r}"
            ) from err
    return out


def load_tariffs(path: Path = TARIFF_FILE) -> list[Tariff]:
    """Load blocks sorted by valid_from; each block inherits unset keys."""
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or []
    if not raw:
        raise ValueError(f"{path.name}: no tariff blocks")
    dated: list[tuple[date, dict[str, Any]]] = []
    for i, block in enumerate(raw):
        if not isinstance(block, dict) or "valid_from" not in block:
            raise ValueError(f"tariff block #{i}: missing valid_from")
        try:
            dated.append((_as_date(block["valid_from"]), block))
        except ValueError as err:
            raise ValueError(f"tariff block #{i}: bad valid_from: {err}") from err
    dated.sort(key=lambda d: d[0])
    out: list[Tariff] = []
    elec: dict[str, float] = {}
    gas: dict[str, float] = {}
    vat: Any = None
    for day, block in dated:
        if out and out[-1].valid_from == day:
            raise ValueError(f"duplicate tariff block {day.isoformat()}")
        for key in block:
            if key not in _BLOCK_KEYS:
                raise ValueError(f"tariff block {day.isoformat()}: unknown key {key}")
        elec = {**elec, **_floats(block.get("electricity") or {}, "electricity", day)}
        gas = {**gas, **_floats(block.get("gas") or {}, "gas", day)}
        if "vat" in block:
            try:
                vat = float(block["vat"])
            except (TypeError, ValueError) as err:
                raise ValueError(
                    f"tariff block {day.isoformat()}: vat not a number: {block['vat']!r}"
                ) from err
        try:
            out.append(
                Tariff(
                    valid_from=day,
                    source=str(block["source"]).strip(),
                    electricity=Electricity(**elec),
                    gas=Gas(**gas),
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
        group, _, field = key.partition(".")
        if group not in _GROUPS or field not in {f.name for f in fields(_GROUPS[group])}:
            raise ValueError(f"unknown override {key}")
        if value is None or value == "":
            continue
        try:
            parts[group][field] = float(str(value).replace(",", "."))
        except ValueError as err:
            raise ValueError(f"override {key}: not a number: {value!r}") from err
    return replace(
        t,
        electricity=replace(t.electricity, **parts["electricity"]),
        gas=replace(t.gas, **parts["gas"]),
    )
