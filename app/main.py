"""Сборка процесса API."""

import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager, suppress

from fastapi import FastAPI

from app.api.payments import router
from app.outbox import run_relay


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    relay = asyncio.create_task(run_relay())
    try:
        yield
    finally:
        relay.cancel()
        with suppress(asyncio.CancelledError):
            await relay


app = FastAPI(title="Payments", lifespan=lifespan)
app.include_router(router)
