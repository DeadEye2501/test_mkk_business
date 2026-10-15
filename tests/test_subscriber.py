import uuid

import pytest

from app import outbox
from app.consumer import processing
from tests.helpers import make_payment


async def test_processing_failure_reaches_faststream(processed, monkeypatch):
    async def process(payment_id: uuid.UUID) -> None:
        raise RuntimeError("attempts exhausted")

    monkeypatch.setattr(processing, "process_payment", process)
    await make_payment(str(uuid.uuid4()))

    with pytest.raises(RuntimeError, match="attempts exhausted"):
        await outbox.publish_pending()
