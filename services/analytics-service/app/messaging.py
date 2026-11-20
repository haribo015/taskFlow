"""Domain events over RabbitMQ (topic exchange ``taskflow.events``).

Event envelope::

    {"event": "task.created", "occurred_at": "<iso8601>", "actor_id": 1, "data": {...}}
"""

import asyncio
import json
import logging
from collections.abc import Awaitable, Callable, Iterable
from datetime import UTC, datetime
from typing import Any, Protocol

import aio_pika
from aio_pika.abc import AbstractExchange, AbstractIncomingMessage, AbstractRobustConnection
from fastapi import Request

EXCHANGE_NAME = "taskflow.events"
logger = logging.getLogger(__name__)

EventHandler = Callable[[str, dict[str, Any]], Awaitable[None]]


class EventPublisher(Protocol):
    async def publish(
        self, routing_key: str, data: dict[str, Any], *, actor_id: int | None = None
    ) -> None: ...


def build_event(routing_key: str, data: dict[str, Any], actor_id: int | None) -> dict[str, Any]:
    return {
        "event": routing_key,
        "occurred_at": datetime.now(UTC).isoformat(),
        "actor_id": actor_id,
        "data": data,
    }


async def connect_with_retry(
    url: str, *, attempts: int = 10, delay: float = 3.0
) -> AbstractRobustConnection:
    for attempt in range(1, attempts + 1):
        try:
            return await aio_pika.connect_robust(url)
        except (ConnectionError, OSError, aio_pika.exceptions.AMQPError) as exc:
            if attempt == attempts:
                raise
            logger.warning("RabbitMQ not ready (%s), retry %d/%d", exc, attempt, attempts)
            await asyncio.sleep(delay)
    raise RuntimeError("unreachable")


async def declare_exchange(connection: AbstractRobustConnection) -> AbstractExchange:
    channel = await connection.channel()
    return await channel.declare_exchange(EXCHANGE_NAME, aio_pika.ExchangeType.TOPIC, durable=True)


class RabbitMQPublisher:
    def __init__(self, url: str) -> None:
        self._url = url
        self._connection: AbstractRobustConnection | None = None
        self._exchange: AbstractExchange | None = None

    async def start(self) -> None:
        self._connection = await connect_with_retry(self._url)
        self._exchange = await declare_exchange(self._connection)
        logger.info("Event publisher connected to RabbitMQ")

    async def publish(
        self, routing_key: str, data: dict[str, Any], *, actor_id: int | None = None
    ) -> None:
        if self._exchange is None:
            logger.warning("Publisher not started, dropping event %s", routing_key)
            return
        message = aio_pika.Message(
            body=json.dumps(build_event(routing_key, data, actor_id), default=str).encode(),
            content_type="application/json",
            delivery_mode=aio_pika.DeliveryMode.PERSISTENT,
        )
        try:
            await self._exchange.publish(message, routing_key=routing_key)
        except Exception:  # an event bus outage must not break the HTTP request
            logger.exception("Failed to publish event %s", routing_key)

    async def close(self) -> None:
        if self._connection is not None:
            await self._connection.close()


class NullPublisher:
    """Used when RabbitMQ is not configured (local runs, unit tests)."""

    async def start(self) -> None:
        logger.info("RABBITMQ_URL not set: events are disabled")

    async def publish(
        self, routing_key: str, data: dict[str, Any], *, actor_id: int | None = None
    ) -> None:
        logger.debug("Event %s not published (no broker)", routing_key)

    async def close(self) -> None:
        return None


def make_publisher(url: str | None) -> RabbitMQPublisher | NullPublisher:
    return RabbitMQPublisher(url) if url else NullPublisher()


def get_publisher(request: Request) -> EventPublisher:
    return request.app.state.publisher


async def start_consumer(
    url: str, queue_name: str, routing_keys: Iterable[str], handler: EventHandler
) -> AbstractRobustConnection:
    """Bind a durable queue to the events exchange and dispatch messages to ``handler``."""
    connection = await connect_with_retry(url)
    channel = await connection.channel()
    await channel.set_qos(prefetch_count=10)
    exchange = await channel.declare_exchange(
        EXCHANGE_NAME, aio_pika.ExchangeType.TOPIC, durable=True
    )
    queue = await channel.declare_queue(queue_name, durable=True)
    for key in routing_keys:
        await queue.bind(exchange, routing_key=key)

    async def on_message(message: AbstractIncomingMessage) -> None:
        # requeue=False: a poison message is dropped instead of looping forever
        async with message.process(requeue=False):
            event = json.loads(message.body)
            await handler(message.routing_key or event.get("event", ""), event)

    await queue.consume(on_message)
    logger.info("Consuming %s on queue %s", list(routing_keys), queue_name)
    return connection
