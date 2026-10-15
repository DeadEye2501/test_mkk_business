"""Тестовое окружение: тестовые база и брокер, известный ключ, нулевые паузы."""

import os

os.environ["DATABASE_URL"] = os.environ["TEST_DATABASE_URL"]
os.environ["AMQP_URL"] = os.environ["TEST_AMQP_URL"]
os.environ["API_KEY"] = "test-key"
os.environ["GATEWAY_DELAY_MIN"] = "0"
os.environ["GATEWAY_DELAY_MAX"] = "0"
os.environ["RETRY_BASE_DELAY"] = "0"
