import uuid

import pytest

from app.models import Payment
from tests.helpers import API_HEADERS, PAYMENT_BODY, api_client, count_rows, post_payment


@pytest.fixture
async def client():
    async with api_client() as client:
        yield client


async def test_create_returns_202_with_pending_payment(client):
    response = await post_payment(client)

    assert response.status_code == 202
    body = response.json()
    assert set(body) == {"payment_id", "status", "created_at"}
    assert body["status"] == "pending"


async def test_repeat_with_same_key_returns_same_payment(client):
    first = await post_payment(client)
    second = await post_payment(client)

    assert second.status_code == 202
    assert second.json()["payment_id"] == first.json()["payment_id"]


async def test_different_keys_create_different_payments(client):
    first = await post_payment(client, key="key-1")
    second = await post_payment(client, key="k" * 255)

    assert second.status_code == 202
    assert second.json()["payment_id"] != first.json()["payment_id"]
    assert await count_rows(Payment) == 2


async def test_get_returns_full_payment(client):
    payment_id = (await post_payment(client)).json()["payment_id"]

    response = await client.get(f"/api/v1/payments/{payment_id}", headers=API_HEADERS)

    assert response.status_code == 200
    body = response.json()
    assert body["id"] == payment_id
    assert body["amount"] == PAYMENT_BODY["amount"]
    assert body["currency"] == PAYMENT_BODY["currency"]
    assert body["description"] == PAYMENT_BODY["description"]
    assert body["metadata"] == PAYMENT_BODY["metadata"]
    assert body["status"] == "pending"
    assert body["idempotency_key"] == "key-1"
    assert body["webhook_url"] == PAYMENT_BODY["webhook_url"]
    assert body["created_at"]
    assert body["processed_at"] is None


async def test_get_unknown_payment_is_404(client):
    response = await client.get(f"/api/v1/payments/{uuid.uuid4()}", headers=API_HEADERS)

    assert response.status_code == 404


@pytest.mark.parametrize(
    "headers", [{}, {"X-API-Key": "wrong"}, {"X-API-Key": "ключ".encode()}]
)
async def test_requests_without_valid_api_key_are_401(client, headers):
    created = await post_payment(client, headers=headers)
    read = await client.get(f"/api/v1/payments/{uuid.uuid4()}", headers=headers)

    assert created.status_code == 401
    assert read.status_code == 401
    assert await count_rows(Payment) == 0


async def test_missing_idempotency_key_is_422(client):
    response = await client.post("/api/v1/payments", json=PAYMENT_BODY, headers=API_HEADERS)

    assert response.status_code == 422
    assert await count_rows(Payment) == 0


@pytest.mark.parametrize("key", ["", "k" * 256])
async def test_empty_or_too_long_idempotency_key_is_422(client, key):
    response = await post_payment(client, key=key)

    assert response.status_code == 422
    assert await count_rows(Payment) == 0


@pytest.mark.parametrize(
    "change",
    [
        {"amount": "10.005"},
        {"amount": "0"},
        {"amount": "-5.00"},
        {"amount": "1" * 17 + ".00"},
        {"currency": "GBP"},
        {"webhook_url": "not a url"},
        {"metadata": ["not", "an", "object"]},
    ],
)
async def test_invalid_body_is_422_and_creates_nothing(client, change):
    response = await post_payment(client, body={**PAYMENT_BODY, **change})

    assert response.status_code == 422
    assert await count_rows(Payment) == 0
