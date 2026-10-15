"""Отправка уведомления о результате платежа."""

import httpx

from app.models import Payment
from app.schemas import WebhookPayload

WEBHOOK_TIMEOUT = 10.0


async def send_webhook(payment: Payment) -> None:
    payload = WebhookPayload.model_validate(payment).model_dump(mode="json")
    async with httpx.AsyncClient(timeout=WEBHOOK_TIMEOUT) as client:
        response = await client.post(payment.webhook_url, json=payload)
    response.raise_for_status()
