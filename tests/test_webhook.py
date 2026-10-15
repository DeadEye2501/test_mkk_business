import uuid

import httpx
import pytest

from app.consumer.webhook import send_webhook
from app.models import Payment, PaymentStatus
from tests.helpers import UNREACHABLE_URL, make_payment, record_payment_result


async def _succeeded(webhook_url: str) -> Payment:
    payment = await make_payment(str(uuid.uuid4()), webhook_url)
    return await record_payment_result(payment.id, PaymentStatus.succeeded)


async def test_webhook_posts_result_of_payment(webhook_receiver):
    payment = await _succeeded(webhook_receiver.url)

    await send_webhook(payment)

    assert webhook_receiver.received == [
        {
            "payment_id": str(payment.id),
            "status": "succeeded",
            "amount": "99.90",
            "currency": "EUR",
            "processed_at": payment.processed_at.isoformat().replace("+00:00", "Z"),
        }
    ]


async def test_non_2xx_answer_is_an_error(webhook_receiver):
    webhook_receiver.statuses.append(500)
    payment = await _succeeded(webhook_receiver.url)

    with pytest.raises(httpx.HTTPStatusError):
        await send_webhook(payment)


async def test_unreachable_endpoint_is_an_error():
    payment = await _succeeded(UNREACHABLE_URL)

    with pytest.raises(httpx.TransportError):
        await send_webhook(payment)
