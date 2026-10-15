"""Внешние формы платежа."""

from decimal import Decimal
from typing import Any

from pydantic import BaseModel, Field, HttpUrl

from app.models import AMOUNT_DECIMAL_PLACES, AMOUNT_MAX_DIGITS, Currency


class PaymentCreate(BaseModel):
    amount: Decimal = Field(
        gt=0, max_digits=AMOUNT_MAX_DIGITS, decimal_places=AMOUNT_DECIMAL_PLACES
    )
    currency: Currency
    description: str
    metadata: dict[str, Any]
    webhook_url: HttpUrl
