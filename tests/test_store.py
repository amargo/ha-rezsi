from datetime import date

from custom_components.rezsi.store import PeriodStore


async def test_default_and_persist(hass, hass_storage):
    s = PeriodStore(hass, "e1")
    await s.async_load(date(2025, 11, 20))
    assert s.period_start == date(2025, 11, 20)
    assert s.previous is None

    await s.async_set_start(date(2026, 1, 5))
    await s.async_close_period(date(2026, 11, 20), {"villany_piaci_aron": 1000})

    s2 = PeriodStore(hass, "e1")
    await s2.async_load(date(2000, 1, 1))
    assert s2.period_start == date(2026, 11, 20)
    assert s2.previous == {"villany_piaci_aron": 1000, "idoszak_vege": "2026-11-20"}
