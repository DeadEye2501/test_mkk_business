from collections import Counter

from app.config import settings
from app.consumer import gateway
from app.models import PaymentStatus
from tests.helpers import record_sleeps


async def test_charge_succeeds_about_nine_times_in_ten():
    outcomes = Counter([await gateway.charge() for _ in range(2000)])

    assert set(outcomes) == {PaymentStatus.succeeded, PaymentStatus.failed}
    assert 0.85 < outcomes[PaymentStatus.succeeded] / 2000 < 0.95


async def test_charge_pauses_anywhere_between_configured_bounds(monkeypatch):
    pauses = record_sleeps(monkeypatch, gateway)
    monkeypatch.setattr(settings, "gateway_delay_min", 2.0)
    monkeypatch.setattr(settings, "gateway_delay_max", 5.0)

    for _ in range(500):
        await gateway.charge()

    assert all(2.0 <= pause <= 5.0 for pause in pauses)
    assert min(pauses) < 2.5
    assert max(pauses) > 4.5
