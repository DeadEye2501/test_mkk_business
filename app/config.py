"""Настройки окружения."""

from pydantic import Field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str
    amqp_url: str
    api_key: str = Field(min_length=1)
    gateway_delay_min: float = 2.0
    gateway_delay_max: float = 5.0
    retry_base_delay: float = 1.0


settings = Settings()
