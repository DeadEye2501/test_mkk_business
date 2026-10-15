import asyncio
import uuid
from contextlib import suppress
from unittest.mock import AsyncMock

import pytest
from sqlalchemy import select

from app import outbox
from app.broker import broker
from app.db import session_factory
from app.models import OutboxEvent
from tests.helpers import api_client, count_rows, make_payment, post_payment, record_sleeps


async def _unpublished() -> list[OutboxEvent]:
    async with session_factory() as session:
        return (await session.scalars(select(OutboxEvent).where(OutboxEvent.published_at.is_(None)))).all()


async def test_pending_events_reach_consumer_in_order_and_are_marked(processed):
    first = await make_payment(str(uuid.uuid4()))
    second = await make_payment(str(uuid.uuid4()))

    assert await outbox.publish_pending() == 2

    assert processed == [first.id, second.id]
    assert await _unpublished() == []
    assert await outbox.publish_pending() == 0


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
    from app.main import app, lifespan

    declare = AsyncMock(side_effect=ConnectionError("broker is down"))
    monkeypatch.setattr(outbox, "declare_topology", declare)

    async with lifespan(app), api_client() as client:
        response = await post_payment(client)

    assert response.status_code == 202
    assert await count_rows(OutboxEvent) == 1
    declare.assert_awaited()
