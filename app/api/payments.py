"""Роутер платежей."""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app import payments
from app.api.auth import require_api_key
from app.db import get_session
from app.models import IDEMPOTENCY_KEY_MAX_LENGTH, Payment
from app.schemas import PaymentAccepted, PaymentCreate, PaymentRead

router = APIRouter(prefix="/api/v1/payments", dependencies=[Depends(require_api_key)])

DbSession = Annotated[AsyncSession, Depends(get_session)]
IdempotencyKey = Annotated[str, Header(min_length=1, max_length=IDEMPOTENCY_KEY_MAX_LENGTH)]


@router.post("", status_code=status.HTTP_202_ACCEPTED, response_model=PaymentAccepted)
async def create_payment(
    data: PaymentCreate, idempotency_key: IdempotencyKey, session: DbSession
) -> Payment:
    return await payments.create_payment(session, data, idempotency_key)


@router.get("/{payment_id}", response_model=PaymentRead)
async def read_payment(payment_id: uuid.UUID, session: DbSession) -> Payment:
    payment = await payments.get_payment(session, payment_id)
    if payment is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Payment not found")
    return payment
