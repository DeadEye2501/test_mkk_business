"""Общие помощники тестов."""

from decimal import Decimal

from sqlalchemy import func, select

from app.db import session_factory
from app.models import Currency, Payment
from app.payments import create_payment
from app.schemas import PaymentCreate

UNREACHABLE_URL = "http://127.0.0.1:9/hook"

PAYMENT_DATA = PaymentCreate(
    amount=Decimal("99.90"),
    currency=Currency.EUR,
    description="subscription",
    metadata={"plan": "pro"},
    webhook_url=UNREACHABLE_URL,
)


async def count_rows(model) -> int:
    async with session_factory() as session:
        return await session.scalar(select(func.count()).select_from(model))


async def make_payment(key: str, webhook_url: str = UNREACHABLE_URL) -> Payment:
    data = PAYMENT_DATA.model_copy(update={"webhook_url": webhook_url})
    async with session_factory() as session:
        return await create_payment(session, data, key)
