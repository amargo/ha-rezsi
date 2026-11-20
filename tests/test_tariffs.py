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


def test_before_first_block_uses_first(tmp_path):
    ts = load_tariffs(write(tmp_path, BASE))
    assert tariff_for(ts, date(2025, 12, 31)) is ts[0]
    assert tariff_for(ts, date(2000, 1, 1)) is ts[0]


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


def test_override_unknown_key(tmp_path):
    t = tariff_for(load_tariffs(write(tmp_path, BASE)), date(2026, 6, 1))
    with pytest.raises(ValueError, match="unknown override electricity.markt"):
        apply_overrides(t, {"electricity.markt": 1})
    with pytest.raises(ValueError, match="unknown override water.market"):
        apply_overrides(t, {"water.market": 1})
    with pytest.raises(ValueError, match="unknown override market"):
        apply_overrides(t, {"market": 1})


def test_override_comma_decimal_and_zero(tmp_path):
    t = tariff_for(load_tariffs(write(tmp_path, BASE)), date(2026, 6, 1))
    o = apply_overrides(t, {"electricity.market": "99,5", "gas.market": 0})
    assert o.electricity.market == 99.5
    assert o.gas.market == 0


def test_override_bad_value(tmp_path):
    t = tariff_for(load_tariffs(write(tmp_path, BASE)), date(2026, 6, 1))
    with pytest.raises(ValueError, match="override gas.market: not a number: 'abc'"):
        apply_overrides(t, {"gas.market": "abc"})


def test_override_leaves_original_unchanged(tmp_path):
    t = tariff_for(load_tariffs(write(tmp_path, BASE)), date(2026, 6, 1))
    apply_overrides(t, {"electricity.market": 1})
    assert t.electricity.market == 130


def test_packaged_file_details():
    ts = load_tariffs(TARIFF_FILE)
    assert tariff_for(ts, date(2027, 6, 1)).electricity.rhd_kwh_extra == -2.08
    assert all(t.source for t in ts)


def test_out_of_order_blocks(tmp_path):
    lines = BASE.strip().split("- valid_from: 2027-01-01")
    swapped = "- valid_from: 2027-01-01" + lines[1] + "\n" + lines[0]
    ts = load_tariffs(write(tmp_path, swapped))
    assert [t.valid_from for t in ts] == [date(2026, 1, 1), date(2027, 1, 1)]
    assert ts[1].electricity.market == 140


def test_duplicate_valid_from(tmp_path):
    with pytest.raises(ValueError, match="duplicate"):
        load_tariffs(write(tmp_path, BASE + "- valid_from: 2027-01-01\n  source: dup\n"))


def test_unknown_yaml_key(tmp_path):
    with pytest.raises(ValueError, match="2027-01-01.*unknown key.*markt"):
        load_tariffs(write(tmp_path, BASE.replace("{market: 140}", "{markt: 140}")))
    with pytest.raises(ValueError, match="2027-01-01.*unknown key colour"):
        load_tariffs(write(tmp_path, BASE.replace("source: next", "source: next\n  colour: 1")))


def test_missing_valid_from_and_bad_number(tmp_path):
    with pytest.raises(ValueError, match="valid_from"):
        load_tariffs(write(tmp_path, "- source: x\n"))
    with pytest.raises(ValueError, match="2027-01-01"):
        load_tariffs(write(tmp_path, BASE.replace("{market: 140}", "{market: abc}")))
