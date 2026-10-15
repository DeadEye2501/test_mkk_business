from decimal import Decimal

from app.db import session_factory
from app.models import Currency, Payment, PaymentStatus
from tests.helpers import UNREACHABLE_URL


async def test_stored_payment_reads_back_with_defaults_filled():
    async with session_factory() as session:
        payment = Payment(
            amount=Decimal("10.55"),
            currency=Currency.USD,
            description="order 42",
            meta={"order": 42, "tags": ["a"]},
            idempotency_key="key-1",
            webhook_url=UNREACHABLE_URL,
        )
        session.add(payment)
        await session.commit()

    async with session_factory() as session:
        stored = await session.get_one(Payment, payment.id)

    assert stored.amount == Decimal("10.55")
    assert stored.meta == {"order": 42, "tags": ["a"]}
    assert stored.status is PaymentStatus.pending
    assert stored.created_at is not None
    assert stored.processed_at is None
