"""Сборка процесса API."""

from fastapi import FastAPI

from app.api.payments import router

app = FastAPI(title="Payments")
app.include_router(router)
