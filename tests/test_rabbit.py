import json
import uuid

import pytest

from app import outbox
from app.broker import dead_letter_queue, declare_topology, new_payments_queue
from app.consumer.subscriber import broker
from app.models import PaymentStatus
from tests.helpers import UNREACHABLE_URL, make_payment, poll

pytestmark = pytest.mark.rabbit


@pytest.fixture
async def running_consumer():
    await declare_topology()
    for queue in (new_payments_queue, dead_letter_queue):
        await (await broker.declare_queue(queue)).purge()
    await broker.start()
    yield
    await broker.stop()


async def test_consumer_processes_event_and_sends_webhook(running_consumer, webhook_receiver):
    payment = await make_payment(str(uuid.uuid4()), webhook_receiver.url)

    await outbox.publish_pending()

    hooks = await webhook_receiver.wait()
    assert hooks[0]["payment_id"] == str(payment.id)
    assert hooks[0]["status"] in {PaymentStatus.succeeded, PaymentStatus.failed}


async def test_undeliverable_webhook_lands_in_dlq(running_consumer):
    payment = await make_payment(str(uuid.uuid4()), UNREACHABLE_URL)
    dlq = await broker.declare_queue(dead_letter_queue)

    await outbox.publish_pending()

    message = await poll(lambda: dlq.get(fail=False))
    await message.ack()
    assert json.loads(message.body) == {"payment_id": str(payment.id)}
