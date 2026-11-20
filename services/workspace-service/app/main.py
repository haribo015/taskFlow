import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI
from tortoise.contrib.fastapi import RegisterTortoise

from app.clients import UserDirectory
from app.config import Settings, get_settings
from app.messaging import make_publisher
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
            httpx.AsyncClient(base_url=settings.user_service_url, timeout=5.0) as http,
        ):
            publisher = make_publisher(settings.rabbitmq_url)
            await publisher.start()
            app.state.publisher = publisher
            app.state.user_directory = UserDirectory(http)
            try:
                yield
            finally:
                await publisher.close()

    app = FastAPI(
        title="TaskFlow - WorkspaceService",
        version="1.0.0",
        lifespan=lifespan,
        docs_url="/api/workspaces/docs",
        openapi_url="/api/workspaces/openapi.json",
    )
    app.include_router(router)

    @app.get("/health", tags=["health"])
    async def health() -> dict[str, str]:
        return {"status": "ok", "service": settings.service_name}

    return app


app = create_app()
