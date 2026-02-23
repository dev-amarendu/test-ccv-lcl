"""Async Firestore client singleton for CCV."""

from __future__ import annotations

from google.cloud.firestore_v1 import AsyncClient

from shared.config import get_settings

_client: AsyncClient | None = None


def get_firestore_client() -> AsyncClient:
    """Return a cached async Firestore client."""
    global _client
    if _client is None:
        settings = get_settings()
        _client = AsyncClient(
            project=settings.firestore_project_id or settings.google_cloud_project,
            database=settings.firestore_database,
        )
    return _client


async def get_db() -> AsyncClient:  # type: ignore[misc]
    """FastAPI dependency that yields the Firestore client."""
    yield get_firestore_client()
