"""Эмуляция платёжного шлюза."""

import asyncio
import random

from app.config import settings
from app.models import PaymentStatus

SUCCESS_RATE = 0.9


async def charge() -> PaymentStatus:
    await asyncio.sleep(random.uniform(settings.gateway_delay_min, settings.gateway_delay_max))
    if random.random() < SUCCESS_RATE:
        return PaymentStatus.succeeded
    return PaymentStatus.failed
