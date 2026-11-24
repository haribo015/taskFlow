#!/usr/bin/env python3
"""Create the TaskFlow Kubernetes Secret without committing credentials."""

from __future__ import annotations

import json
import secrets
import subprocess
from pathlib import Path
from urllib.parse import quote

ROOT = Path(__file__).resolve().parent.parent
ENV_FILE = ROOT / ".k8s.env"
REQUIRED = ("POSTGRES_USER", "POSTGRES_PASSWORD", "RABBITMQ_USER", "RABBITMQ_PASSWORD", "JWT_SECRET")


def credentials() -> dict[str, str]:
    if not ENV_FILE.exists():
        values = {
            "POSTGRES_USER": "taskflow",
            "POSTGRES_PASSWORD": secrets.token_urlsafe(24),
            "RABBITMQ_USER": "taskflow",
            "RABBITMQ_PASSWORD": secrets.token_urlsafe(24),
            "JWT_SECRET": secrets.token_urlsafe(48),
        }
        ENV_FILE.write_text(
            "# Local Kubernetes credentials. Keep this file; PostgreSQL and RabbitMQ persist data.\n"
            + "".join(f"{key}={value}\n" for key, value in values.items()),
            encoding="utf-8",
        )
        ENV_FILE.chmod(0o600)
        print(f"Created {ENV_FILE.name} (ignored by Git)")

    values: dict[str, str] = {}
    for line in ENV_FILE.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#"):
            key, separator, value = line.partition("=")
            if not separator:
                raise ValueError(f"Invalid line in {ENV_FILE.name}: {key}")
            values[key.strip()] = value.strip()
    if any(not values.get(key) for key in REQUIRED):
        raise ValueError(f"{ENV_FILE.name} must define {', '.join(REQUIRED)}")
    if len(values["JWT_SECRET"]) < 32:
        raise ValueError("JWT_SECRET must have at least 32 characters")
    return values


def secret_data(values: dict[str, str]) -> dict[str, str]:
    pg_user = quote(values["POSTGRES_USER"], safe="")
    pg_password = quote(values["POSTGRES_PASSWORD"], safe="")
    rabbit_user = quote(values["RABBITMQ_USER"], safe="")
    rabbit_password = quote(values["RABBITMQ_PASSWORD"], safe="")
    data = {key: values[key] for key in REQUIRED}
    for service, database in (
        ("USERS", "users_db"),
        ("WORKSPACES", "workspaces_db"),
        ("TASKS", "tasks_db"),
        ("ANALYTICS", "analytics_db"),
    ):
        data[f"{service}_DATABASE_URL"] = (
            f"postgres://{pg_user}:{pg_password}@postgres:5432/{database}"
        )
    data["RABBITMQ_URL"] = f"amqp://{rabbit_user}:{rabbit_password}@rabbitmq:5672/"
    return data


def main() -> None:
    payload = {
        "apiVersion": "v1",
        "kind": "Secret",
        "metadata": {"name": "taskflow-secrets", "namespace": "taskflow"},
        "type": "Opaque",
        "stringData": secret_data(credentials()),
    }
    subprocess.run(["kubectl", "apply", "-f", "-"], input=json.dumps(payload), text=True, check=True)


if __name__ == "__main__":
    main()
