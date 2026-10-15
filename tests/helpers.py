"""Общие помощники тестов."""

import asyncio
import json
import threading
from collections.abc import AsyncIterator, Iterator
from contextlib import asynccontextmanager, contextmanager
from dataclasses import dataclass, field
from decimal import Decimal
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from types import SimpleNamespace

import httpx
from sqlalchemy import func, select

from app.config import settings
from app.db import session_factory
from app.main import app, lifespan
from app.models import Currency, Payment, PaymentStatus
from app.payments import create_payment, get_payment, record_result
from app.schemas import PaymentCreate

UNREACHABLE_URL = "http://127.0.0.1:9/hook"
POLL_TIMEOUT = 20.0

PAYMENT_DATA = PaymentCreate(
    amount=Decimal("99.90"),
    currency=Currency.EUR,
    description="subscription",
    metadata={"plan": "pro"},
    webhook_url=UNREACHABLE_URL,
)

API_HEADERS = {"X-API-Key": settings.api_key}
PAYMENT_BODY = PAYMENT_DATA.model_dump(mode="json")


async def count_rows(model) -> int:
    async with session_factory() as session:
        return await session.scalar(select(func.count()).select_from(model))


async def make_payment(key: str, webhook_url: str = UNREACHABLE_URL) -> Payment:
    data = PAYMENT_DATA.model_copy(update={"webhook_url": webhook_url})
    async with session_factory() as session:
        return await create_payment(session, data, key)


async def record_payment_result(payment_id, status: PaymentStatus) -> Payment:
    async with session_factory() as session:
        return await record_result(session, payment_id, status)


async def stored_payment(payment_id) -> Payment | None:
    async with session_factory() as session:
        return await get_payment(session, payment_id)


async def poll(check):
    loop = asyncio.get_running_loop()
    deadline = loop.time() + POLL_TIMEOUT
    while not (result := await check()):
        assert loop.time() < deadline, "timed out waiting"
        await asyncio.sleep(0.2)
    return result


@dataclass
class WebhookReceiver:
    url: str
    received: list[dict] = field(default_factory=list)
    statuses: list[int] = field(default_factory=list)

    def answer(self, body: bytes) -> int:
        self.received.append(json.loads(body))
        return self.statuses.pop(0) if self.statuses else 200

    async def wait(self) -> list[dict]:
        return await poll(self._received)

    async def _received(self) -> list[dict]:
        return self.received


@contextmanager
def serving_webhooks() -> Iterator[WebhookReceiver]:
    class Handler(BaseHTTPRequestHandler):
        def do_POST(self) -> None:
            body = self.rfile.read(int(self.headers["Content-Length"]))
            self.send_response(receiver.answer(body))
            self.end_headers()

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    receiver = WebhookReceiver(url=f"http://127.0.0.1:{server.server_port}/hook")
    threading.Thread(target=server.serve_forever, daemon=True).start()
    try:
        yield receiver
    finally:
        server.shutdown()
        server.server_close()


def record_sleeps(monkeypatch, module) -> list[float]:
    pauses: list[float] = []

    async def sleep(delay: float) -> None:
        pauses.append(delay)

    monkeypatch.setattr(module, "asyncio", SimpleNamespace(sleep=sleep))
    return pauses


@asynccontextmanager
async def api_client() -> AsyncIterator[httpx.AsyncClient]:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        yield client


@asynccontextmanager
async def running_api() -> AsyncIterator[httpx.AsyncClient]:
    async with lifespan(app), api_client() as client:
        yield client


async def post_payment(
    client: httpx.AsyncClient, body=PAYMENT_BODY, key: str = "key-1", headers=API_HEADERS
) -> httpx.Response:
    return await client.post(
        "/api/v1/payments", json=body, headers={**headers, "Idempotency-Key": key}
    )
