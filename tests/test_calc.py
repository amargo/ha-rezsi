from dataclasses import replace
from datetime import date, timedelta

import pytest

from custom_components.rezsi.calc import CalcOptions, DayUsage, compute, tier
from custom_components.rezsi.tariffs import Electricity, Gas, Tariff

T26 = Tariff(
    valid_from=date(2026, 1, 1),
    source="test",
    electricity=Electricity(36.06, 70.10, 2523, 130, 15, 0, 0),
    gas=Gas(102, 747, 1729, 500),
    vat=27,
)
T27 = replace(T26, valid_from=date(2027, 1, 1), source="t27",
              electricity=replace(T26.electricity, market=200, rhd_base_extra=12930, rhd_kwh_extra=-2.08))
START = date(2026, 1, 1)


def year(imp=3580.0, exp=2295.0, gas=1304.0, days=365, start=START):
    """All quantity on day 0, zeros after: band depends only on day count."""
    out = [DayUsage(start, imp, exp, gas)]
    out += [DayUsage(start + timedelta(n)) for n in range(1, days)]
    return out


def only26(_day):
    return T26


def test_tier():
    assert tier(100, 50, 1, 2) == 150
    assert tier(10, 50, 1, 2) == 10


def test_szaldo_reference():
    r = compute(year(), only26, CalcOptions(szaldo=True))
    assert r.billed_kwh == pytest.approx(1285)
    assert r.elec_reg == pytest.approx(46337.10)
    assert r.elec_mkt == pytest.approx(167050)
    assert r.credit == 0


def test_gross_reference():
    r = compute(year(), only26, CalcOptions(szaldo=False))
    assert r.credit == pytest.approx(34425)
    assert r.elec_reg == pytest.approx(130650.08)
    assert r.elec_mkt == pytest.approx(430975)


def test_gas_reference_and_multiplier():
    r = compute(year(), only26, CalcOptions())
    assert r.gas_reg == pytest.approx(133008)
    assert r.gas_mkt == pytest.approx(652000)
    r1 = compute(year(gas=3000), only26, CalcOptions(gas_band_mult=1))
    r2 = compute(year(gas=3000), only26, CalcOptions(gas_band_mult=2))
    assert r1.gas_reg == pytest.approx(1729 * 102 + 1271 * 747)
    assert r2.gas_reg == pytest.approx(3000 * 102)
    assert r2.gas_band_m3 == pytest.approx(3458)


def test_rhd_market_only():
    t = lambda _d: replace(T26, electricity=replace(T26.electricity, rhd_base_extra=12930, rhd_kwh_extra=-2.08))
    off = compute(year(), t, CalcOptions(rhd=False))
    on = compute(year(), t, CalcOptions(rhd=True))
    assert on.rhd == pytest.approx(13026.644)
    assert on.elec_mkt - off.elec_mkt == pytest.approx(13026.644)
    assert on.elec_reg == off.elec_reg


def test_half_period_band():
    r = compute(year(imp=3580, exp=2295, days=182), only26, CalcOptions())
    assert r.band_kwh == pytest.approx(1258.0438, rel=1e-6)
    assert r.elec_reg == pytest.approx(47254.6879, rel=1e-6)
    assert r.band_used_pct == pytest.approx(1285 / 1258.0438 * 100, rel=1e-6)


def test_tariff_change_inside_period():
    usage = [DayUsage(date(2026, 12, 22) + timedelta(n), imp=10) for n in range(20)]
    pick = lambda d: T27 if d >= T27.valid_from else T26
    r = compute(usage, pick, CalcOptions())
    band = 2523 * 10 / 365
    assert r.elec_mkt == pytest.approx(100 * 130 + 100 * 200)
    assert r.elec_reg == pytest.approx(2 * tier(100, band, 36.06, 70.10))
    assert r.tariff.source == "t27"


def test_monthly_breakdown():
    usage = [DayUsage(date(2026, 1, 31), 5, 1, 2), DayUsage(date(2026, 2, 1), 7, 0, 3)]
    r = compute(usage, only26, CalcOptions())
    assert r.monthly == {
        "2026-01": {"vetel_kwh": 5.0, "betaplalas_kwh": 1.0, "gaz_m3": 2.0},
        "2026-02": {"vetel_kwh": 7.0, "betaplalas_kwh": 0.0, "gaz_m3": 3.0},
    }


def test_empty_usage():
    with pytest.raises(ValueError):
        compute([], only26, CalcOptions())
