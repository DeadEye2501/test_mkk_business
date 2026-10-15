"""Запуск миграций Alembic на асинхронном движке."""

import asyncio

from alembic import context
from sqlalchemy import Connection

from app.db import engine
from app.models import Base


def _run_migrations(connection: Connection) -> None:
    context.configure(connection=connection, target_metadata=Base.metadata)
    with context.begin_transaction():
        context.run_migrations()


async def _run_async_migrations() -> None:
    async with engine.connect() as connection:
        await connection.run_sync(_run_migrations)
    await engine.dispose()


asyncio.run(_run_async_migrations())
