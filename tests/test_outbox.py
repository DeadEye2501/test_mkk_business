import asyncio
import uuid
from contextlib import suppress
from datetime import timedelta
from unittest.mock import AsyncMock

import pytest
from sqlalchemy import func, select, update

from app import outbox
from app.broker import broker
from app.db import session_factory
from app.models import OutboxEvent
from tests.helpers import count_rows, make_payment, post_payment, record_sleeps, running_api


async def _unpublished() -> list[OutboxEvent]:
    async with session_factory() as session:
        return (await session.scalars(select(OutboxEvent).where(OutboxEvent.published_at.is_(None)))).all()


async def test_pending_events_reach_consumer_and_are_marked(processed):
    first = await make_payment(str(uuid.uuid4()))
    second = await make_payment(str(uuid.uuid4()))

    assert await outbox.publish_pending() == 2

    assert processed == [first.id, second.id]
    assert await _unpublished() == []
    assert await outbox.publish_pending() == 0


async def test_events_go_out_in_created_at_order(processed):
    inserted_first = await make_payment(str(uuid.uuid4()))
    inserted_second = await make_payment(str(uuid.uuid4()))
    async with session_factory() as session, session.begin():
        await session.execute(
            update(OutboxEvent)
            .where(OutboxEvent.payload == {"payment_id": str(inserted_second.id)})
            .values(created_at=func.now() - timedelta(minutes=1))
        )

    await outbox.publish_pending()

    assert processed == [inserted_second.id, inserted_first.id]


async def test_one_call_publishes_at_most_one_batch(processed, monkeypatch):
    monkeypatch.setattr(outbox, "BATCH_SIZE", 2)
    for _ in range(3):
        await make_payment(str(uuid.uuid4()))

    assert await outbox.publish_pending() == 2
    assert await outbox.publish_pending() == 1


async def test_events_are_published_as_persistent_messages(monkeypatch):
    await make_payment(str(uuid.uuid4()))
    publish = AsyncMock()
    monkeypatch.setattr(broker, "publish", publish)

    await outbox.publish_pending()

    assert publish.await_args.kwargs["persist"] is True


async def test_failed_publish_leaves_event_for_next_iteration(monkeypatch):
    payment = await make_payment(str(uuid.uuid4()))

    async def broken(message, **kwargs) -> None:
        raise ConnectionError("broker is down")

    monkeypatch.setattr(broker, "publish", broken)
    with pytest.raises(ConnectionError):
        await outbox.publish_pending()

    assert [event.payload for event in await _unpublished()] == [{"payment_id": str(payment.id)}]


async def test_relay_iteration_pauses_unless_batch_was_full(monkeypatch):
    pauses = record_sleeps(monkeypatch, outbox)
    outcomes = [outbox.BATCH_SIZE, 1, ConnectionError("broker is down")]
    monkeypatch.setattr(outbox, "declare_topology", AsyncMock())
    monkeypatch.setattr(outbox, "publish_pending", AsyncMock(side_effect=outcomes))

    await outbox._relay_iteration()
    assert pauses == []
    await outbox._relay_iteration()
    await outbox._relay_iteration()
    assert pauses == [outbox.POLL_INTERVAL, outbox.POLL_INTERVAL]


async def test_stopped_relay_closes_broker_connection(monkeypatch):
    stop = AsyncMock()
    monkeypatch.setattr(broker, "stop", stop)
    monkeypatch.setattr(outbox, "declare_topology", AsyncMock())
    monkeypatch.setattr(outbox, "publish_pending", AsyncMock(return_value=0))

    relay = asyncio.create_task(outbox.run_relay())
    await asyncio.sleep(0)
    relay.cancel()
    with suppress(asyncio.CancelledError):
        await relay

    stop.assert_awaited_once()


async def test_api_accepts_payments_while_broker_is_down(monkeypatch):
    declare = AsyncMock(side_effect=ConnectionError("broker is down"))
    monkeypatch.setattr(outbox, "declare_topology", declare)

    async with running_api() as client:
        response = await post_payment(client)

    assert response.status_code == 202
    assert await count_rows(OutboxEvent) == 1
    declare.assert_awaited()
