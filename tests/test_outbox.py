import uuid

import pytest
from sqlalchemy import select

from app import outbox
from app.broker import broker
from app.db import session_factory
from app.models import OutboxEvent
from tests.helpers import make_payment


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
