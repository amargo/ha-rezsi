"""Daily consumption from recorder long-term statistics."""
from __future__ import annotations

from datetime import date, timedelta

from homeassistant.components.recorder import get_instance
from homeassistant.components.recorder.statistics import statistics_during_period
from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util


async def async_daily_changes(
    hass: HomeAssistant, stat_ids: dict[str, str | None], start: date, end: date
) -> dict[str, dict[date, float]]:
    """Return {key: {local day: change}} for start..end (inclusive).

    A configured key is always present; its dict is empty when there are no rows
    (callers check emptiness, not membership). Rows without a change are skipped.
    """
    wanted = {k: v for k, v in stat_ids.items() if v}
    if not wanted:
        return {}
    start_dt = dt_util.start_of_local_day(start)
    end_dt = dt_util.start_of_local_day(end + timedelta(days=1))
    rows = await get_instance(hass).async_add_executor_job(
        statistics_during_period,
        hass,
        start_dt,
        end_dt,
        set(wanted.values()),
        "day",
        None,
        {"change"},
    )
    out: dict[str, dict[date, float]] = {}
    for key, sid in wanted.items():
        out[key] = {
            dt_util.as_local(dt_util.utc_from_timestamp(r["start"])).date(): float(r["change"])
            for r in rows.get(sid, [])
            if r.get("change") is not None
        }
    return out
