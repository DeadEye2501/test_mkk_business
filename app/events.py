"""Формат события payments.new."""

import uuid

from pydantic import BaseModel


class PaymentCreated(BaseModel):
    payment_id: uuid.UUID
