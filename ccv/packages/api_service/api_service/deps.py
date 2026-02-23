"""Shared FastAPI dependencies."""

from __future__ import annotations

from google.cloud.firestore_v1 import AsyncClient

from shared.config import Settings, get_settings
from shared.firestore_client import get_db


async def db_session() -> AsyncClient:  # type: ignore[misc]
    """Yield the Firestore async client."""
    async for client in get_db():
        yield client


def settings() -> Settings:
    """Return the cached application settings singleton."""
    return get_settings()
