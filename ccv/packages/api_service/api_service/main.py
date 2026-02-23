"""FastAPI application entry-point for the CCV API Service."""

from __future__ import annotations

import uuid

from fastapi import FastAPI, Request, Response

from shared.config import get_settings
from shared.logging import get_logger, set_request_id, setup_logging

from api_service.routes import (
    artifacts,
    audit,
    branches,
    findings,
    health,
    kb_under_findings,
    repos,
    scans_manual,
    schedules,
    tasks,
    webhooks,
)

settings = get_settings()
setup_logging(settings.api_log_level)
logger = get_logger(__name__)

app = FastAPI(
    title="CCV API Service",
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
)


# ── Middleware: request_id propagation ────────────────────────────────────────


@app.middleware("http")
async def request_id_middleware(request: Request, call_next) -> Response:
    """Inject or propagate X-Request-Id on every request."""
    rid = request.headers.get("x-request-id") or uuid.uuid4().hex[:16]
    set_request_id(rid)
    logger.debug("request_start", method=request.method, path=request.url.path)
    response: Response = await call_next(request)
    response.headers["X-Request-Id"] = rid
    return response


# ── Routes ────────────────────────────────────────────────────────────────────

# Health at root (no /api prefix)
app.include_router(health.router)

# Pub/Sub push subscription handlers
app.include_router(tasks.router, prefix="/pubsub")

# All other routers under /api
app.include_router(repos.router, prefix="/api")
app.include_router(branches.router, prefix="/api")
app.include_router(artifacts.router, prefix="/api")
app.include_router(scans_manual.router, prefix="/api")
app.include_router(schedules.router, prefix="/api")
app.include_router(findings.router, prefix="/api")
app.include_router(kb_under_findings.router, prefix="/api")
app.include_router(webhooks.router, prefix="/api")
app.include_router(audit.router, prefix="/api")


def main() -> None:
    """Run the API with uvicorn (dev mode)."""
    import uvicorn

    uvicorn.run(
        "api_service.main:app",
        host=settings.api_host,
        port=settings.api_port,
        log_level=settings.api_log_level,
        reload=True,
    )


if __name__ == "__main__":
    main()
