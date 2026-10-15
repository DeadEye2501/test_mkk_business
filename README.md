# Payments - асинхронный процессинг платежей

Микросервис принимает платёж по API, обрабатывает его через эмуляцию платёжного
шлюза и сообщает результат на webhook клиента.

## Стек

- Python 3.13, FastAPI, Pydantic v2
- SQLAlchemy 2.0 (async, asyncpg), PostgreSQL, Alembic
- RabbitMQ, FastStream
- httpx
- Docker, docker-compose
- pytest

## Как работает

1. `POST /api/v1/payments` одной транзакцией пишет платёж (`pending`) и событие в таблицу `outbox`.
2. Relay в процессе API публикует неопубликованные события в обменник `payments`
   с ключом `payments.new`, дожидается подтверждения брокера и отмечает события
   опубликованными (outbox pattern, доставка at-least-once). Если брокер недоступен,
   API продолжает принимать платежи - события ждут в outbox.
3. Consumer читает очередь `payments.new` по одному сообщению: эмулирует шлюз
   (2–5 с, 90% `succeeded`, 10% `failed`), записывает итог и шлёт webhook.
   Итог пишется один раз: повторная доставка сообщения шлюз заново не запускает.
4. Ошибка на любом шаге - повтор: всего 3 попытки, паузы 1 с и 2 с. После третьей
   неудачи сообщение отклоняется и через обменник `payments.dlx` попадает в
   очередь `payments.new.dlq`.

Повтор `POST` с тем же `Idempotency-Key` возвращает уже созданный платёж.
Все эндпоинты требуют заголовок `X-API-Key`.

## Webhook

`POST` на `webhook_url` с телом:

    {"payment_id": "…", "status": "succeeded", "amount": "150.00",
     "currency": "RUB", "processed_at": "…"}

- `amount` передаётся строкой.
- Доставленным считается только ответ 2xx. Перенаправление (3xx), ошибка
  сервера, таймаут 10 с или недоступный адрес - неудачная попытка.
- Webhook может прийти повторно с тем же итогом (доставка at-least-once).
- Webhook не подписан; итог можно подтвердить запросом `GET /api/v1/payments/{payment_id}`.

## Переменные окружения

| Переменная | Назначение |
|---|---|
| `DATABASE_URL` | `postgresql+asyncpg://...` |
| `AMQP_URL` | строка подключения к RabbitMQ |
| `API_KEY` | ключ для заголовка `X-API-Key`, непустой |
| `GATEWAY_DELAY_MIN`, `GATEWAY_DELAY_MAX` | границы паузы шлюза, по умолчанию 2 и 5 с |
| `RETRY_BASE_DELAY` | базовая задержка повтора, по умолчанию 1 с |
| `TEST_DATABASE_URL` | база для тестов; тесты пересоздают в ней схему и очищают таблицы |
| `TEST_AMQP_URL` | брокер для тестов; тесты очищают его очереди |

## Запуск через Docker Compose

    API_KEY=secret docker compose up --build

В PowerShell - `$env:API_KEY="secret"; docker compose up --build`. Без `API_KEY`
ключом будет `change-me`; примеры ниже используют `secret`.

API - `http://localhost:8000`, панель RabbitMQ - `http://localhost:15672` (guest/guest).

## Локальный запуск

Нужны Python 3.13, pipenv, PostgreSQL и RabbitMQ. Создать две базы - рабочую и
тестовую (`payments` и `payments_test`), скопировать `.env.example` в `.env`, заполнить.

    pipenv install --dev
    pipenv run alembic upgrade head
    pipenv run uvicorn app.main:app
    pipenv run faststream run app.consumer.main:app

## Примеры

Создать платёж:

    curl -X POST http://localhost:8000/api/v1/payments \
      -H "X-API-Key: secret" \
      -H "Idempotency-Key: 3f1c2b9e-order-7" \
      -H "Content-Type: application/json" \
      -d '{"amount": "150.00", "currency": "RUB", "description": "order 7",
           "metadata": {"order_id": 7}, "webhook_url": "https://webhook.site/<ваш-id>"}'

Ответ `202`:

    {"payment_id": "…", "status": "pending", "created_at": "…"}

Получить платёж:

    curl http://localhost:8000/api/v1/payments/<payment_id> -H "X-API-Key: secret"

## Тесты

Для любого прогона должны быть заданы `TEST_DATABASE_URL` и `TEST_AMQP_URL`.

Без настоящего брокера:

    pipenv run pytest

Против настоящего RabbitMQ из `TEST_AMQP_URL` (доставка в DLQ, подтверждения):

    pipenv run pytest -m rabbit
