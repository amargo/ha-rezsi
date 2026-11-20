from datetime import timedelta
from unittest.mock import patch

from homeassistant import config_entries
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.util import dt as dt_util
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.rezsi.const import (
    CONF_ELEC_MULT, CONF_GAS, CONF_GAS_MULT, CONF_IMPORT, CONF_OVERRIDES, CONF_RHD, CONF_SZALDO, DOMAIN,
)

USER = {"name": "Velencei ház", CONF_IMPORT: "sensor.imp", CONF_GAS: "sensor.gas", CONF_SZALDO: True}


async def test_user_flow(hass):
    with patch("custom_components.rezsi.async_setup_entry", return_value=True):
        r = await hass.config_entries.flow.async_init(DOMAIN, context={"source": config_entries.SOURCE_USER})
        assert r["type"] is FlowResultType.FORM
        r = await hass.config_entries.flow.async_configure(r["flow_id"], USER)
    assert r["type"] is FlowResultType.CREATE_ENTRY
    assert r["title"] == "Velencei ház"
    assert r["data"][CONF_IMPORT] == "sensor.imp"
    assert "name" not in r["data"]


async def test_duplicate_name(hass):
    MockConfigEntry(domain=DOMAIN, unique_id="velencei_haz", title="Velencei ház").add_to_hass(hass)
    r = await hass.config_entries.flow.async_init(DOMAIN, context={"source": config_entries.SOURCE_USER})
    r = await hass.config_entries.flow.async_configure(r["flow_id"], USER)
    assert r["type"] is FlowResultType.ABORT
    assert r["reason"] == "already_configured"


async def test_options_flow(hass):
    entry = MockConfigEntry(domain=DOMAIN, unique_id="x", title="X", data={CONF_IMPORT: "sensor.imp", CONF_SZALDO: True})
    entry.add_to_hass(hass)
    with patch("custom_components.rezsi.async_setup_entry", return_value=True):
        r = await hass.config_entries.options.async_init(entry.entry_id)
        assert r["type"] is FlowResultType.FORM
        r = await hass.config_entries.options.async_configure(
            r["flow_id"],
            {CONF_SZALDO: False, CONF_ELEC_MULT: 2, CONF_GAS_MULT: 1, CONF_RHD: True, "electricity.market": 150},
        )
    assert r["type"] is FlowResultType.CREATE_ENTRY
    assert entry.options[CONF_ELEC_MULT] == 2
    assert entry.options[CONF_RHD] is True
    assert entry.options[CONF_OVERRIDES] == {"electricity.market": 150}


async def test_duplicate_name_slug(hass):
    MockConfigEntry(domain=DOMAIN, unique_id="velencei_haz", title="Velencei ház").add_to_hass(hass)
    r = await hass.config_entries.flow.async_init(DOMAIN, context={"source": config_entries.SOURCE_USER})
    r = await hass.config_entries.flow.async_configure(r["flow_id"], {**USER, "name": "velencei haz"})
    assert r["type"] is FlowResultType.ABORT
    assert r["reason"] == "already_configured"


async def test_invalid_name(hass):
    r = await hass.config_entries.flow.async_init(DOMAIN, context={"source": config_entries.SOURCE_USER})
    r = await hass.config_entries.flow.async_configure(r["flow_id"], {**USER, "name": "!!!"})
    assert r["type"] is FlowResultType.FORM
    assert r["errors"] == {"base": "invalid_name"}


async def test_period_start_default(hass):
    with patch("custom_components.rezsi.async_setup_entry", return_value=True):
        r = await hass.config_entries.flow.async_init(DOMAIN, context={"source": config_entries.SOURCE_USER})
        r = await hass.config_entries.flow.async_configure(r["flow_id"], USER)
    expected = (dt_util.now().date() - timedelta(days=364)).isoformat()  # 365 days incl. today
    assert r["data"]["period_start"] == expected


async def test_options_no_overrides(hass):
    entry = MockConfigEntry(domain=DOMAIN, unique_id="x", title="X", data={CONF_IMPORT: "sensor.imp"})
    entry.add_to_hass(hass)
    with patch("custom_components.rezsi.async_setup_entry", return_value=True):
        r = await hass.config_entries.options.async_init(entry.entry_id)
        r = await hass.config_entries.options.async_configure(
            r["flow_id"], {CONF_SZALDO: True, CONF_ELEC_MULT: 1, CONF_GAS_MULT: 1, CONF_RHD: False}
        )
    assert r["type"] is FlowResultType.CREATE_ENTRY
    assert entry.options[CONF_OVERRIDES] == {}
