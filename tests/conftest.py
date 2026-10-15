"""Общее окружение тестов: тестовая база, схема из миграций, чистые таблицы."""

import os

import pytest
from alembic import command
from alembic.config import Config

os.environ["DATABASE_URL"] = os.environ["TEST_DATABASE_URL"]
os.environ["API_KEY"] = "test-key"
os.environ["GATEWAY_DELAY_MIN"] = "0"
os.environ["GATEWAY_DELAY_MAX"] = "0"
os.environ["RETRY_BASE_DELAY"] = "0"


@pytest.fixture(scope="session", autouse=True)
def migrated_database() -> None:
    config = Config("alembic.ini")
    command.downgrade(config, "base")
    command.upgrade(config, "head")


@pytest.fixture(autouse=True)
async def clean_tables():
    from sqlalchemy import text

    from app.db import engine
    from app.models import Base

    tables = ", ".join(table.name for table in Base.metadata.sorted_tables)
    async with engine.begin() as connection:
        await connection.execute(text(f"TRUNCATE {tables}"))
    yield
    await engine.dispose()
