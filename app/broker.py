"""Настройка RabbitMQ: соединение, обменники, очереди."""

from faststream.rabbit import Channel, ExchangeType, RabbitBroker, RabbitExchange, RabbitQueue

from app.config import settings

NEW_PAYMENTS = "payments.new"

broker = RabbitBroker(settings.amqp_url, default_channel=Channel(prefetch_count=1))

payments_exchange = RabbitExchange("payments", type=ExchangeType.DIRECT)
dead_letter_exchange = RabbitExchange("payments.dlx", type=ExchangeType.DIRECT)
new_payments_queue = RabbitQueue(
    NEW_PAYMENTS,
    routing_key=NEW_PAYMENTS,
    arguments={"x-dead-letter-exchange": dead_letter_exchange.name},
)
dead_letter_queue = RabbitQueue(f"{NEW_PAYMENTS}.dlq", routing_key=NEW_PAYMENTS)


async def declare_topology() -> None:
    await broker.connect()
    exchange = await broker.declare_exchange(payments_exchange)
    dlx = await broker.declare_exchange(dead_letter_exchange)
    queue = await broker.declare_queue(new_payments_queue)
    await queue.bind(exchange, routing_key=new_payments_queue.routing())
    dlq = await broker.declare_queue(dead_letter_queue)
    await dlq.bind(dlx, routing_key=dead_letter_queue.routing())
