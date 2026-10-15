import asyncio
import uuid

import httpx
import pytest

from app.consumer import gateway, processing
from app.db import session_factory
from app.models import Payment, PaymentStatus
from app.payments import get_payment
from tests.helpers import make_payment, record_sleeps


async def _stored(payment_id) -> Payment:
    async with session_factory() as session:
        return await get_payment(session, payment_id)


async def _payment_for(receiver) -> Payment:
    return await make_payment(str(uuid.uuid4()), receiver.url)


def _gateway_returning(monkeypatch, *statuses: PaymentStatus) -> list[PaymentStatus]:
    calls: list[PaymentStatus] = []
    queue = list(statuses)

    async def charge() -> PaymentStatus:
        await asyncio.sleep(0.05)
        calls.append(queue.pop(0))
        return calls[-1]

    monkeypatch.setattr(gateway, "charge", charge)
    return calls


async def test_pending_payment_gets_result_recorded_and_sent(webhook_receiver, monkeypatch):
    _gateway_returning(monkeypatch, PaymentStatus.failed)
    payment = await _payment_for(webhook_receiver)

    await processing.process_payment(payment.id)

    stored = await _stored(payment.id)
    assert stored.status is PaymentStatus.failed
    assert stored.processed_at is not None
    assert [hook["status"] for hook in webhook_receiver.received] == ["failed"]


async def test_redelivered_payment_is_not_charged_again(webhook_receiver, monkeypatch):
    calls = _gateway_returning(monkeypatch, PaymentStatus.succeeded, PaymentStatus.failed)
    payment = await _payment_for(webhook_receiver)

    await processing.process_payment(payment.id)
    await processing.process_payment(payment.id)

    assert calls == [PaymentStatus.succeeded]
    assert [hook["status"] for hook in webhook_receiver.received] == ["succeeded", "succeeded"]


async def test_failed_webhook_is_retried_without_new_charge(webhook_receiver, monkeypatch):
    calls = _gateway_returning(monkeypatch, PaymentStatus.succeeded, PaymentStatus.failed)
    webhook_receiver.statuses.extend([500, 503])
    payment = await _payment_for(webhook_receiver)

    await processing.process_payment(payment.id)

    assert calls == [PaymentStatus.succeeded]
    assert len(webhook_receiver.received) == 3
    assert (await _stored(payment.id)).status is PaymentStatus.succeeded


async def test_three_failed_attempts_raise_and_keep_recorded_result(webhook_receiver, monkeypatch):
    _gateway_returning(monkeypatch, PaymentStatus.succeeded)
    webhook_receiver.statuses.extend([500, 500, 500])
    payment = await _payment_for(webhook_receiver)

    with pytest.raises(httpx.HTTPStatusError):
        await processing.process_payment(payment.id)

    assert len(webhook_receiver.received) == 3
    assert (await _stored(payment.id)).status is PaymentStatus.succeeded


async def test_attempts_are_spaced_exponentially(webhook_receiver, monkeypatch):
    _gateway_returning(monkeypatch, PaymentStatus.succeeded)
    webhook_receiver.statuses.extend([500, 500, 500])
    pauses = record_sleeps(monkeypatch, processing)
    monkeypatch.setattr(processing.settings, "retry_base_delay", 1.0)
    payment = await _payment_for(webhook_receiver)

    with pytest.raises(httpx.HTTPStatusError):
        await processing.process_payment(payment.id)

    assert pauses == [1.0, 2.0]


async def test_parallel_copies_send_one_and_the_same_result(webhook_receiver, monkeypatch):
    calls = _gateway_returning(monkeypatch, PaymentStatus.succeeded, PaymentStatus.failed)
    payment = await _payment_for(webhook_receiver)

    await asyncio.gather(
        processing.process_payment(payment.id), processing.process_payment(payment.id)
    )

    recorded = (await _stored(payment.id)).status
    assert len(calls) == 2
    assert [hook["status"] for hook in webhook_receiver.received] == [recorded, recorded]
