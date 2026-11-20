from datetime import date
from pathlib import Path

import pytest

from custom_components.rezsi.tariffs import (
    TARIFF_FILE,
    apply_overrides,
    load_tariffs,
    tariff_for,
)


def write(tmp_path: Path, text: str) -> Path:
    p = tmp_path / "t.yaml"
    p.write_text(text, encoding="utf-8")
    return p


BASE = """
- valid_from: 2026-01-01
  source: base
  electricity: {reduced: 36.06, above: 70.10, band_kwh: 2523, market: 130, feed_in: 15,
                rhd_base_extra: 0, rhd_kwh_extra: 0}
  gas: {reduced: 102, above: 747, band_m3: 1729, market: 500}
  vat: 27
- valid_from: 2027-01-01
  source: next
  electricity: {market: 140}
"""


def test_inheritance_and_lookup(tmp_path):
    ts = load_tariffs(write(tmp_path, BASE))
    t26 = tariff_for(ts, date(2026, 12, 31))
    t27 = tariff_for(ts, date(2027, 1, 1))
    assert t26.electricity.market == 130
    assert t27.electricity.market == 140
    assert t27.electricity.reduced == 36.06
    assert t27.gas.band_m3 == 1729
    assert t27.vat == 27
    assert t27.source == "next"


def test_before_first_block(tmp_path):
    ts = load_tariffs(write(tmp_path, BASE))
    with pytest.raises(ValueError):
        tariff_for(ts, date(2025, 12, 31))


def test_incomplete_first_block(tmp_path):
    bad = "- valid_from: 2026-01-01\n  source: x\n  electricity: {reduced: 1}\n  gas: {}\n  vat: 27\n"
    with pytest.raises(ValueError, match="2026-01-01"):
        load_tariffs(write(tmp_path, bad))


def test_overrides(tmp_path):
    t = tariff_for(load_tariffs(write(tmp_path, BASE)), date(2026, 6, 1))
    o = apply_overrides(t, {"electricity.market": 99, "gas.band_m3": None, "gas.market": ""})
    assert o.electricity.market == 99
    assert o.electricity.reduced == 36.06
    assert o.gas.band_m3 == 1729
    assert o.gas.market == 500


def test_packaged_file_loads():
    ts = load_tariffs(TARIFF_FILE)
    assert ts[0].valid_from == date(2026, 1, 1)
    assert tariff_for(ts, date(2027, 6, 1)).electricity.rhd_base_extra == 12930
