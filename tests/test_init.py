from datetime import timedelta
from unittest.mock import patch

import pytest
from homeassistant.config_entries import ConfigEntryState
from homeassistant.exceptions import ServiceValidationError
from homeassistant.util import dt as dt_util
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.rezsi.const import (
    CONF_EXPORT, CONF_GAS, CONF_IMPORT, CONF_OVERRIDES, CONF_PERIOD_START, CONF_SZALDO, DOMAIN,
)

FETCH = "custom_components.rezsi.coordinator.async_daily_changes"


def fake(imp_total=3580.0, gas_total=1304.0, with_gas=True, lag=0):
    async def _f(hass, ids, start, end):
        out = {"imp": {start + timedelta(days=lag): imp_total}}
        if ids.get("gas"):
            # statistics.py contract: a configured key is always present, {} when no rows
            out["gas"] = {start: gas_total} if with_gas else {}
        return out
    return _f


def entry(hass, title="Velencei ház", gas=True, options=None):
    start = (dt_util.now().date() - timedelta(days=364)).isoformat()  # config flow default: 365 days incl. today
    data = {CONF_IMPORT: "sensor.imp", CONF_SZALDO: False, CONF_PERIOD_START: start}
    if gas:
        data[CONF_GAS] = "sensor.gas"
    e = MockConfigEntry(domain=DOMAIN, title=title, unique_id=title, data=data, options=options or {})
    e.add_to_hass(hass)
    return e


async def setup(hass, e, fetch):
    with patch(FETCH, side_effect=fetch):
        await hass.config_entries.async_setup(e.entry_id)
        await hass.async_block_till_done()


async def test_entities_and_values(recorder_mock, hass):
    e = entry(hass)
    await setup(hass, e, fake())
    reg = hass.states.get("sensor.velencei_haz_villany_rezsiaron")
    mkt = hass.states.get("sensor.velencei_haz_villany_piaci_aron")
    assert float(reg.state) == pytest.approx(165075.08, abs=1)  # gross, no export
    assert float(mkt.state) == pytest.approx(3580 * 130, abs=1)
    assert float(hass.states.get("sensor.velencei_haz_gaz_rezsiaron").state) == pytest.approx(133008, abs=1)
    tot_reg = 165075.08 + 133008
    tot_mkt = 3580 * 130 + 1304 * 500
    diff = hass.states.get("sensor.velencei_haz_kulonbseg")
    assert float(diff.state) == pytest.approx(tot_mkt - tot_reg, abs=1)
    assert diff.attributes["kulonbseg_pct"] == pytest.approx((tot_mkt - tot_reg) / tot_reg * 100, abs=0.1)
    assert float(hass.states.get("sensor.velencei_haz_eves_becsles_piaci").state) == pytest.approx(tot_mkt, abs=1)
    attrs = mkt.attributes
    for key in ("idoszak_kezdete", "eltelt_napok", "vetel_kwh", "betaplalas_kwh", "elszamolt_kwh", "gaz_m3",
                "savhatar_aranyos", "savhatar_felhasznalt_pct", "tarifa_valid_from", "tarifa_forras",
                "havi_bontas", "elozo_idoszak", "adat_hianyos", "elso_adat_napja"):
        assert key in attrs
    assert attrs["eltelt_napok"] == 365
    assert attrs["vetel_kwh"] == 3580
    assert attrs["adat_hianyos"] is False
    assert attrs["idoszak_kezdete"] == e.data[CONF_PERIOD_START]
    assert hass.states.get("button.velencei_haz_leolvasas_most") is not None
    assert hass.states.get("date.velencei_haz_idoszak_kezdete") is not None


async def test_two_sites(recorder_mock, hass):
    a, b = entry(hass, "Velencei ház"), entry(hass, "Pesti lakás", gas=False)
    with patch(FETCH, side_effect=fake()):
        await hass.config_entries.async_setup(a.entry_id)  # domain setup loads every entry
        await hass.async_block_till_done()
    assert a.state is ConfigEntryState.LOADED and b.state is ConfigEntryState.LOADED
    assert hass.states.get("sensor.velencei_haz_villany_piaci_aron") is not None
    assert hass.states.get("sensor.pesti_lakas_villany_piaci_aron") is not None
    assert hass.states.get("sensor.pesti_lakas_gaz_piaci_aron") is None


async def test_gas_missing(recorder_mock, hass):
    e = entry(hass)
    await setup(hass, e, fake(with_gas=False))
    assert hass.states.get("sensor.velencei_haz_gaz_piaci_aron").state == "unavailable"
    assert hass.states.get("sensor.velencei_haz_villany_piaci_aron").state != "unavailable"
    assert float(hass.states.get("sensor.velencei_haz_osszesen_rezsiaron").state) == pytest.approx(
        float(hass.states.get("sensor.velencei_haz_villany_rezsiaron").state))
    assert float(hass.states.get("sensor.velencei_haz_osszesen_piaci_aron").state) == pytest.approx(
        float(hass.states.get("sensor.velencei_haz_villany_piaci_aron").state))


async def test_late_statistics(recorder_mock, hass):
    e = entry(hass)
    await setup(hass, e, fake(lag=10))
    attrs = hass.states.get("sensor.velencei_haz_villany_piaci_aron").attributes
    first = (dt_util.now().date() - timedelta(days=354)).isoformat()
    assert attrs["adat_hianyos"] is True
    assert attrs["elso_adat_napja"] == first


async def test_future_date_rejected(recorder_mock, hass):
    e = entry(hass)
    await setup(hass, e, fake())
    before = hass.states.get("date.velencei_haz_idoszak_kezdete").state
    tomorrow = (dt_util.now().date() + timedelta(days=1)).isoformat()
    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(
            "date", "set_value", {"entity_id": "date.velencei_haz_idoszak_kezdete", "date": tomorrow}, blocking=True
        )
    assert hass.states.get("date.velencei_haz_idoszak_kezdete").state == before


async def test_bad_override_fails_setup(recorder_mock, hass):
    e = entry(hass, options={CONF_OVERRIDES: {"electricity.market": "abc"}})
    await setup(hass, e, fake())
    assert e.state is ConfigEntryState.SETUP_ERROR


async def test_button_and_date(recorder_mock, hass):
    e = entry(hass)
    with patch(FETCH, side_effect=fake()):
        await hass.config_entries.async_setup(e.entry_id)
        await hass.async_block_till_done()
        await hass.services.async_call("button", "press", {"entity_id": "button.velencei_haz_leolvasas_most"}, blocking=True)
        await hass.async_block_till_done()
        today = dt_util.now().date()
        assert hass.states.get("date.velencei_haz_idoszak_kezdete").state == today.isoformat()
        prev = hass.states.get("sensor.velencei_haz_villany_piaci_aron").attributes["elozo_idoszak"]
        assert prev["idoszak_vege"] == today.isoformat()
        assert prev["villany_piaci_aron"] == pytest.approx(3580 * 130, abs=1)

        new = (today - timedelta(days=10)).isoformat()
        await hass.services.async_call("date", "set_value", {"entity_id": "date.velencei_haz_idoszak_kezdete", "date": new}, blocking=True)
        await hass.config_entries.async_reload(e.entry_id)
        await hass.async_block_till_done()
    assert hass.states.get("date.velencei_haz_idoszak_kezdete").state == new


async def test_options_change_reloads(recorder_mock, hass):
    e = entry(hass)
    with patch(FETCH, side_effect=fake()):
        await hass.config_entries.async_setup(e.entry_id)
        await hass.async_block_till_done()
        hass.config_entries.async_update_entry(e, options={CONF_OVERRIDES: {"electricity.market": 200}})
        await hass.async_block_till_done()
    assert e.state is ConfigEntryState.LOADED
    assert float(hass.states.get("sensor.velencei_haz_villany_piaci_aron").state) == pytest.approx(3580 * 200, abs=1)


async def test_empty_fresh_period_stays_available(recorder_mock, hass):
    today = dt_util.now().date()
    inner = fake()

    async def no_rows_today(hass, ids, start, end):
        if start == today:  # just after "Leolvasás most": no statistics row for today yet
            return {"imp": {}, "gas": {}}
        return await inner(hass, ids, start, end)

    e = entry(hass)
    with patch(FETCH, side_effect=no_rows_today):
        await hass.config_entries.async_setup(e.entry_id)
        await hass.async_block_till_done()
        await hass.services.async_call("button", "press", {"entity_id": "button.velencei_haz_leolvasas_most"}, blocking=True)
        await hass.async_block_till_done()
    assert e.state is ConfigEntryState.LOADED
    mkt = hass.states.get("sensor.velencei_haz_villany_piaci_aron")
    assert float(mkt.state) == 0
    assert float(hass.states.get("sensor.velencei_haz_villany_rezsiaron").state) == 0
    assert mkt.attributes["idoszak_kezdete"] == today.isoformat()
    assert mkt.attributes["elozo_idoszak"]["villany_piaci_aron"] == pytest.approx(3580 * 130, abs=1)


async def test_missing_export_warns_once(recorder_mock, hass, caplog):
    e = entry(hass)
    hass.config_entries.async_update_entry(e, data={**e.data, CONF_EXPORT: "sensor.exp"})
    with patch(FETCH, side_effect=fake()):
        await hass.config_entries.async_setup(e.entry_id)
        await hass.async_block_till_done()
        await e.runtime_data.async_refresh()
    assert e.state is ConfigEntryState.LOADED
    assert caplog.text.count("no statistics for export sensor.exp") == 1


async def test_no_import_stats_retries(recorder_mock, hass):
    async def empty(hass, ids, start, end):
        return {"imp": {}}
    e = entry(hass)
    with patch(FETCH, side_effect=empty):
        await hass.config_entries.async_setup(e.entry_id)
        await hass.async_block_till_done()
    assert e.state is ConfigEntryState.SETUP_RETRY
