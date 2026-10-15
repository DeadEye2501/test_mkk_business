import pytest
from pydantic import ValidationError

from app.config import Settings


def test_empty_api_key_is_refused_at_startup(monkeypatch):
    monkeypatch.setenv("API_KEY", "")

    with pytest.raises(ValidationError):
        Settings()
