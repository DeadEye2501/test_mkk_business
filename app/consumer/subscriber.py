"""Подписчик на payments.new: исход обработки → ack / reject."""

from faststream import AckPolicy

from app.broker import broker, new_payments_queue, payments_exchange
from app.consumer import processing
from app.events import PaymentCreated


@broker.subscriber(
    new_payments_queue, payments_exchange, ack_policy=AckPolicy.REJECT_ON_ERROR
)
async def handle_new_payment(event: PaymentCreated) -> None:
    await processing.process_payment(event.payment_id)
