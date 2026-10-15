"""Общее окружение тестов: тестовая база, схема из миграций, чистые таблицы."""

import json
import os
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

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


@pytest.fixture
def webhook_receiver():
    from tests.helpers import WebhookReceiver

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self) -> None:
            length = int(self.headers["Content-Length"])
            receiver.received.append(json.loads(self.rfile.read(length)))
            self.send_response(receiver.statuses.pop(0) if receiver.statuses else 200)
            self.end_headers()

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    receiver = WebhookReceiver(url=f"http://127.0.0.1:{server.server_port}/hook")
    threading.Thread(target=server.serve_forever, daemon=True).start()
    yield receiver
    server.shutdown()
    server.server_close()
