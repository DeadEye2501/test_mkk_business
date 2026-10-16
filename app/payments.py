"""Хранилище платежей."""

import uuid
from typing import Any

from sqlalchemy import func, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.events import PaymentCreated
from app.models import OutboxEvent, Payment, PaymentStatus
from app.schemas import PaymentCreate


class IdempotencyKeyReused(Exception):
    pass


async def create_payment(
    session: AsyncSession, data: PaymentCreate, idempotency_key: str
) -> Payment:
    values = {
        "amount": data.amount,
        "currency": data.currency,
        "description": data.description,
        "meta": data.metadata,
        "webhook_url": str(data.webhook_url),
    }
    statement = (
        insert(Payment)
        .values(**values, idempotency_key=idempotency_key)
        .on_conflict_do_nothing(index_elements=[Payment.idempotency_key])
        .returning(Payment)
    )
    async with session.begin():
        payment = await session.scalar(statement)
        if payment is None:
            return await _stored_with_same_values(session, idempotency_key, values)
        event = PaymentCreated(payment_id=payment.id)
        session.add(OutboxEvent(payload=event.model_dump(mode="json")))
    return payment


async def _stored_with_same_values(
    session: AsyncSession, idempotency_key: str, values: dict[str, Any]
) -> Payment:
    payment = await session.scalar(
        select(Payment).where(Payment.idempotency_key == idempotency_key)
    )
    if any(getattr(payment, name) != value for name, value in values.items()):
        raise IdempotencyKeyReused(idempotency_key)
    return payment


async def get_payment(session: AsyncSession, payment_id: uuid.UUID) -> Payment | None:
    return await session.get(Payment, payment_id)


async def record_result(
    session: AsyncSession, payment_id: uuid.UUID, status: PaymentStatus
) -> Payment:
    statement = (
        update(Payment)
        .where(Payment.id == payment_id, Payment.status == PaymentStatus.pending)
        .values(status=status, processed_at=func.now())
        .returning(Payment)
    )
    async with session.begin():
        recorded = await session.scalar(statement)
        return recorded or await session.get_one(Payment, payment_id)
