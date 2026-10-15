"""Хранилище платежей."""

import uuid

from sqlalchemy import func, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.events import PaymentCreated
from app.models import OutboxEvent, Payment, PaymentStatus
from app.schemas import PaymentCreate


async def create_payment(
    session: AsyncSession, data: PaymentCreate, idempotency_key: str
) -> Payment:
    statement = (
        insert(Payment)
        .values(
            amount=data.amount,
            currency=data.currency,
            description=data.description,
            meta=data.metadata,
            idempotency_key=idempotency_key,
            webhook_url=str(data.webhook_url),
        )
        .on_conflict_do_nothing(index_elements=[Payment.idempotency_key])
        .returning(Payment)
    )
    async with session.begin():
        payment = await session.scalar(statement)
        if payment is None:
            return await session.scalar(
                select(Payment).where(Payment.idempotency_key == idempotency_key)
            )
        event = PaymentCreated(payment_id=payment.id)
        session.add(OutboxEvent(payload=event.model_dump(mode="json")))
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
