"""Relay: публикация событий outbox в RabbitMQ."""

import asyncio
import logging
from datetime import UTC, datetime

from sqlalchemy import select

from app.broker import broker, declare_topology, new_payments_queue, payments_exchange
from app.db import session_factory
from app.models import OutboxEvent

logger = logging.getLogger(__name__)

BATCH_SIZE = 100
POLL_INTERVAL = 1.0


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


async def run_relay() -> None:
    try:
        while True:
            await _relay_iteration()
    finally:
        await broker.stop()


async def _relay_iteration() -> None:
    try:
        await declare_topology()
        if await publish_pending() == BATCH_SIZE:
            return
    except Exception:
        logger.exception("Outbox relay iteration failed")
    await asyncio.sleep(POLL_INTERVAL)
