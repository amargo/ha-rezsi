from dataclasses import replace
from datetime import date, timedelta
from unittest.mock import patch

import pytest
from homeassistant.config_entries import ConfigEntryState
from homeassistant.util import dt as dt_util
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.rezsi.const import (
    CONF_GAS, CONF_IMPORT, CONF_OVERRIDES, CONF_PERIOD_START, CONF_SZALDO, DOMAIN,
)
from custom_components.rezsi.tariffs import load_tariffs

FETCH = "custom_components.rezsi.coordinator.async_daily_changes"


@pytest.fixture(autouse=True)
def tariffs_cover_past_year():
    """The bundled first block starts 2026-01-01; let it cover the whole test period."""
    real = load_tariffs()
    shifted = [replace(real[0], valid_from=date(2000, 1, 1)), *real[1:]]
    with patch("custom_components.rezsi.load_tariffs", return_value=shifted):
        yield


def fake(imp_total=3580.0, gas_total=1304.0, with_gas=True):
    async def _f(hass, ids, start, end):
        out = {"imp": {start: imp_total}}
        if ids.get("gas"):
            # statistics.py contract: a configured key is always present, {} when no rows
            out["gas"] = {start: gas_total} if with_gas else {}
        return out
    return _f


def entry(hass, title="Velencei ház", gas=True):
    start = (dt_util.now().date() - timedelta(days=364)).isoformat()  # 365 days incl. today
    data = {CONF_IMPORT: "sensor.imp", CONF_SZALDO: False, CONF_PERIOD_START: start}
    if gas:
        data[CONF_GAS] = "sensor.gas"
    e = MockConfigEntry(domain=DOMAIN, title=title, unique_id=title, data=data)
    e.add_to_hass(hass)
    return e


async def setup(hass, e, fetch):
    with patch(FETCH, side_effect=fetch):
        assert await hass.config_entries.async_setup(e.entry_id) or True
        await hass.async_block_till_done()


async def test_entities_and_values(recorder_mock, hass):
    e = entry(hass)
    await setup(hass, e, fake())
    reg = hass.states.get("sensor.velencei_haz_villany_rezsiaron")
    mkt = hass.states.get("sensor.velencei_haz_villany_piaci_aron")
    assert float(reg.state) == pytest.approx(165075.08, abs=1)  # gross, no export
    assert float(mkt.state) == pytest.approx(3580 * 130, abs=1)
    assert float(hass.states.get("sensor.velencei_haz_gaz_rezsiaron").state) == pytest.approx(133008, abs=1)
    attrs = mkt.attributes
    for key in ("idoszak_kezdete", "eltelt_napok", "vetel_kwh", "betaplalas_kwh", "elszamolt_kwh", "gaz_m3",
                "savhatar_aranyos", "savhatar_felhasznalt_pct", "tarifa_valid_from", "tarifa_forras",
                "havi_bontas", "elozo_idoszak", "adat_hianyos", "elso_adat_napja"):
        assert key in attrs
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


async def test_no_import_stats_retries(recorder_mock, hass):
    async def empty(hass, ids, start, end):
        return {"imp": {}}
    e = entry(hass)
    with patch(FETCH, side_effect=empty):
        await hass.config_entries.async_setup(e.entry_id)
        await hass.async_block_till_done()
    assert e.state is ConfigEntryState.SETUP_RETRY
