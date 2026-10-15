"""Обработка события payments.new."""

import asyncio
import logging
import uuid

from app import payments
from app.config import settings
from app.consumer import gateway, webhook
from app.db import session_factory
from app.models import PaymentStatus

logger = logging.getLogger(__name__)

MAX_ATTEMPTS = 3


async def process_payment(payment_id: uuid.UUID) -> None:
    for attempt in range(1, MAX_ATTEMPTS + 1):
        try:
            await _attempt(payment_id)
            return
        except Exception:
            logger.exception("Payment %s: attempt %d of %d failed", payment_id, attempt, MAX_ATTEMPTS)
            if attempt == MAX_ATTEMPTS:
                raise
            await asyncio.sleep(settings.retry_base_delay * 2 ** (attempt - 1))


async def _attempt(payment_id: uuid.UUID) -> None:
    async with session_factory() as session:
        payment = await payments.get_payment(session, payment_id)
    if payment.status is PaymentStatus.pending:
        status = await gateway.charge()
        async with session_factory() as session:
            payment = await payments.record_result(session, payment_id, status)
    await webhook.send_webhook(payment)
