import asyncio
import uuid

from sqlalchemy import select

from app.db import session_factory
from app.models import OutboxEvent, Payment, PaymentStatus
from app.payments import get_payment
from tests.helpers import count_rows, make_payment, record_payment_result


async def test_new_payment_is_pending_and_leaves_one_event_naming_it():
    payment = await make_payment("key-1")

    assert payment.status is PaymentStatus.pending
    async with session_factory() as session:
        events = (await session.scalars(select(OutboxEvent))).all()
    assert [event.payload for event in events] == [{"payment_id": str(payment.id)}]
    assert events[0].published_at is None


async def test_repeat_with_same_key_returns_same_payment_without_new_event():
    first = await make_payment("key-1")
    second = await make_payment("key-1")

    assert second.id == first.id
    assert await count_rows(Payment) == 1
    assert await count_rows(OutboxEvent) == 1


async def test_concurrent_requests_with_same_key_create_one_payment():
    first, second = await asyncio.gather(make_payment("race"), make_payment("race"))

    assert first.id == second.id
    assert await count_rows(Payment) == 1
    assert await count_rows(OutboxEvent) == 1


async def test_get_payment_returns_none_for_unknown_id():
    async with session_factory() as session:
        assert await get_payment(session, uuid.uuid4()) is None


async def test_result_is_recorded_once_and_later_writes_get_it_back():
    payment = await make_payment("key-1")

    first = await record_payment_result(payment.id, PaymentStatus.failed)
    second = await record_payment_result(payment.id, PaymentStatus.succeeded)

    assert first.status is PaymentStatus.failed
    assert first.processed_at is not None
    assert second.status is PaymentStatus.failed
    assert second.processed_at == first.processed_at
