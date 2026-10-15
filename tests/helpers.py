"""Общие помощники тестов."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from decimal import Decimal

import httpx
from sqlalchemy import func, select

from app.config import settings
from app.db import session_factory
from app.main import app
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

API_HEADERS = {"X-API-Key": settings.api_key}
PAYMENT_BODY = PAYMENT_DATA.model_dump(mode="json")


async def count_rows(model) -> int:
    async with session_factory() as session:
        return await session.scalar(select(func.count()).select_from(model))


async def make_payment(key: str, webhook_url: str = UNREACHABLE_URL) -> Payment:
    data = PAYMENT_DATA.model_copy(update={"webhook_url": webhook_url})
    async with session_factory() as session:
        return await create_payment(session, data, key)


@asynccontextmanager
async def api_client() -> AsyncIterator[httpx.AsyncClient]:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        yield client


async def post_payment(
    client: httpx.AsyncClient, body=PAYMENT_BODY, key: str = "key-1", headers=API_HEADERS
) -> httpx.Response:
    return await client.post(
        "/api/v1/payments", json=body, headers={**headers, "Idempotency-Key": key}
    )
