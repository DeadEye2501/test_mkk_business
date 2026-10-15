"""Сборка процесса consumer."""

from faststream import FastStream

from app.broker import declare_topology
from app.consumer.subscriber import broker

app = FastStream(broker, on_startup=[declare_topology])
