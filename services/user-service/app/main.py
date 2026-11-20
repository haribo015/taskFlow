import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from tortoise.contrib.fastapi import RegisterTortoise

from app.config import Settings, get_settings
from app.routers import auth_router, users_router

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")

MODELS = {"models": ["app.models"]}


def create_app(settings: Settings | None = None, *, init_db: bool = True) -> FastAPI:
    settings = settings or get_settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        if not init_db:
            yield
            return
        async with RegisterTortoise(
            app, db_url=settings.database_url, modules=MODELS, generate_schemas=True
        ):
            yield

    app = FastAPI(
        title="TaskFlow - UserService",
        version="1.0.0",
        lifespan=lifespan,
        docs_url="/api/users/docs",
        openapi_url="/api/users/openapi.json",
    )
    app.include_router(auth_router)
    app.include_router(users_router)

    @app.get("/health", tags=["health"])
    async def health() -> dict[str, str]:
        return {"status": "ok", "service": settings.service_name}

    return app


app = create_app()
