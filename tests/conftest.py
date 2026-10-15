"""Фикстуры тестов."""

import pytest
from alembic import command
from alembic.config import Config
from faststream.rabbit import TestRabbitBroker
from sqlalchemy import text

from app.consumer import processing
from app.consumer.subscriber import broker
from app.db import engine
from app.models import Base
from tests.helpers import serving_webhooks


@pytest.fixture(scope="session", autouse=True)
def migrated_database() -> None:
    config = Config("alembic.ini")
    command.downgrade(config, "base")
    command.upgrade(config, "head")


@pytest.fixture(autouse=True)
async def clean_tables():
    tables = ", ".join(table.name for table in Base.metadata.sorted_tables)
    async with engine.begin() as connection:
        await connection.execute(text(f"TRUNCATE {tables}"))
    yield
    await engine.dispose()


@pytest.fixture
def webhook_receiver():
    with serving_webhooks() as receiver:
        yield receiver


@pytest.fixture
async def processed(monkeypatch):
    payment_ids = []

    async def process(payment_id) -> None:
        payment_ids.append(payment_id)

    monkeypatch.setattr(processing, "process_payment", process)
    async with TestRabbitBroker(broker):
        yield payment_ids
