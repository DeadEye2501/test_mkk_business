"""Relay: публикация событий outbox в RabbitMQ."""

from datetime import UTC, datetime

from sqlalchemy import select

from app.broker import broker, new_payments_queue, payments_exchange
from app.db import session_factory
from app.models import OutboxEvent

BATCH_SIZE = 100


async def publish_pending() -> int:
    statement = (
        select(OutboxEvent)
        .where(OutboxEvent.published_at.is_(None))
        .order_by(OutboxEvent.created_at)
        .limit(BATCH_SIZE)
    )
    async with session_factory() as session, session.begin():
        events = (await session.scalars(statement)).all()
        for event in events:
            await broker.publish(
                event.payload,
                exchange=payments_exchange,
                routing_key=new_payments_queue.routing(),
                persist=True,
            )
            event.published_at = datetime.now(UTC)
    return len(events)
