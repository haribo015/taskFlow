from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    service_name: str = "workspace-service"
    database_url: str = "sqlite://:memory:"
    jwt_secret: str = "dev-only-insecure-secret-change-me-in-prod"
    jwt_algorithm: str = "HS256"
    rabbitmq_url: str | None = None
    user_service_url: str = "http://user-service:8000"


@lru_cache
def get_settings() -> Settings:
    return Settings()
