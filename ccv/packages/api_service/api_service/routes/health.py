"""Health and version endpoints (mounted at root, not under /api)."""

from __future__ import annotations

from fastapi import APIRouter

from shared.firestore_client import get_firestore_client
from shared.schemas import HealthResponse

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse)
async def health_check() -> HealthResponse:
    """Liveness / readiness probe — verifies Firestore connectivity."""
    try:
        client = get_firestore_client()
        # Quick connectivity check: list one collection
        async for _ in client.collections():
            break
        return HealthResponse(status="ok", service="ccv-api")
    except Exception:
        return HealthResponse(status="degraded", service="ccv-api")


@router.get("/version")
async def version() -> dict:
    """Return service version metadata."""
    return {"version": "0.1.0", "service": "ccv-api"}
