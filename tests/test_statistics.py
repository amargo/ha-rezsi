from datetime import date, timedelta

from unittest.mock import patch

import pytest

from homeassistant.components.recorder.statistics import async_import_statistics
from homeassistant.util import dt as dt_util
from pytest_homeassistant_custom_component.components.recorder.common import (
    async_wait_recording_done,
)

from custom_components.rezsi.statistics import async_daily_changes


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(recorder_mock, enable_custom_integrations):
    """Override conftest: recorder_mock must be set up before hass."""
    yield


def _metadata(stat_id: str, unit: str) -> dict:
    meta = {
        "has_mean": False,
        "has_sum": True,
        "name": None,
        "source": "recorder",
        "statistic_id": stat_id,
        "unit_of_measurement": unit,
        "unit_class": "energy",
    }
    try:  # HA >= 2025.6
        from homeassistant.components.recorder.models import StatisticMeanType

        meta["mean_type"] = StatisticMeanType.NONE
    except ImportError:
        pass
    return meta


async def test_daily_changes(recorder_mock, hass):
    await hass.config.async_set_time_zone("Europe/Budapest")
    today = dt_util.now().date()
    d0 = today - timedelta(days=3)
    stats = []
    total = 0.0
    for n, per_hour in enumerate((1.0, 2.0, 0.5)):  # 24, 48, 12 per day
        start = dt_util.start_of_local_day(d0 + timedelta(n))
        for h in range(24):
            total += per_hour
            stats.append({"start": start + timedelta(hours=h), "sum": total, "state": total})
    async_import_statistics(hass, _metadata("sensor.imp", "kWh"), stats)
    await async_wait_recording_done(hass)

    out = await async_daily_changes(hass, {"imp": "sensor.imp", "gas": None}, d0, today)
    # today has no data -> absent
    assert out == {
        "imp": {
            d0: 24.0,
            d0 + timedelta(1): 48.0,
            d0 + timedelta(2): 12.0,
        }
    }


async def test_unknown_statistic_id(recorder_mock, hass):
    today = dt_util.now().date()
    out = await async_daily_changes(hass, {"imp": "sensor.nope"}, today - timedelta(days=3), today)
    assert out == {"imp": {}}


async def test_no_ids(hass):
    with patch("custom_components.rezsi.statistics.get_instance") as gi:
        assert await async_daily_changes(hass, {"imp": None}, date(2026, 1, 1), date(2026, 1, 2)) == {}
    gi.assert_not_called()
