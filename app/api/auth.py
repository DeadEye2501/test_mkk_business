"""Проверка X-API-Key."""

import secrets
from typing import Annotated

from fastapi import Header, HTTPException, status

from app.config import settings


async def require_api_key(x_api_key: Annotated[str, Header()] = "") -> None:
    if not secrets.compare_digest(x_api_key.encode(), settings.api_key.encode()):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid API key")
