import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI
from tortoise.contrib.fastapi import RegisterTortoise

from app.clients import WorkspaceDirectory
from app.config import Settings, get_settings
from app.events import QUEUE_NAME, ROUTING_KEYS, handle_event
from app.messaging import start_consumer
from app.routers import router

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")

MODELS = {"models": ["app.models"]}


def create_app(settings: Settings | None = None, *, init_resources: bool = True) -> FastAPI:
    settings = settings or get_settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        if not init_resources:  # tests wire their own fakes
            yield
            return
        async with (
            RegisterTortoise(
                app, db_url=settings.database_url, modules=MODELS, generate_schemas=True
            ),
            httpx.AsyncClient(base_url=settings.workspace_service_url, timeout=5.0) as http,
        ):
            consumer = None
            if settings.rabbitmq_url:
                consumer = await start_consumer(
                    settings.rabbitmq_url, QUEUE_NAME, ROUTING_KEYS, handle_event
                )
            else:
                logging.getLogger(__name__).warning("RABBITMQ_URL not set: no events consumed")
            app.state.workspace_directory = WorkspaceDirectory(http)
            try:
                yield
            finally:
                if consumer is not None:
                    await consumer.close()

    app = FastAPI(
        title="TaskFlow - AnalyticsService",
        version="1.0.0",
        lifespan=lifespan,
        docs_url="/api/analytics/docs",
        openapi_url="/api/analytics/openapi.json",
    )
    app.include_router(router)

    @app.get("/health", tags=["health"])
    async def health() -> dict[str, str]:
        return {"status": "ok", "service": settings.service_name}

    return app


app = create_app()
