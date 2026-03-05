"""Optional FastAPI KB service for Fix Cards retrieval.

Endpoints:
    GET  /kb/v1/cards/{cwe_id}
    GET  /kb/v1/search?q=&topK=
    POST /kb/v1/admin/cards/upsert
"""

from __future__ import annotations

import uuid
from typing import cast

from fastapi import FastAPI, HTTPException, Query, Request, Response

from shared.config import get_settings
from shared.firestore_models import KBFixCardDoc
from shared.logging import get_logger, set_request_id, setup_logging
from shared.schemas import (
    KBFixCardCreateRequest,
    KBFixCardResponse,
    KBSearchResponse,
    KBSearchResult,
)

from kb_service.embeddings import embed_text
from kb_service.store import get_fix_card, upsert_fix_card, vector_search

settings = get_settings()
setup_logging(settings.api_log_level)
logger = get_logger(__name__)

app = FastAPI(title="CCV KB Service", version="0.1.0")


@app.middleware("http")
async def request_id_middleware(request: Request, call_next) -> Response:
    rid = request.headers.get("x-request-id") or uuid.uuid4().hex[:16]
    set_request_id(rid)
    response: Response = await call_next(request)
    response.headers["X-Request-Id"] = rid
    return response


@app.get("/health")
async def health() -> dict:
    return {"status": "ok", "service": "ccv-kb"}


@app.get("/kb/v1/cards/{cwe_id}", response_model=KBFixCardResponse)
async def get_card(cwe_id: int) -> KBFixCardResponse:
    """Retrieve a Fix Card by CWE ID."""
    card = await get_fix_card(cwe_id)
    if not card:
        raise HTTPException(404, f"Fix Card for CWE-{cwe_id} not found")
    
    # Map KBFixCardDoc to Response
    return KBFixCardResponse(
        id=card.id, cwe_id=card.cwe_id, title=card.title, tags=card.tags,
        summary=card.summary, fix_steps_json=card.fix_steps_json,
        content=card.content, source=card.source, approved=card.approved,
        original_finding_id=card.original_finding_id,
        usage_count=card.usage_count,
        created_at=card.created_at, updated_at=card.updated_at,
    )


@app.get("/kb/v1/search", response_model=KBSearchResponse)
async def search_cards(
    q: str = Query(..., min_length=1, description="Search query"),
    top_k: int = Query(5, ge=1, le=50, alias="topK"),
) -> KBSearchResponse:
    """Semantic search across Fix Cards using Vertex AI Vector Search."""
    results = await vector_search(q, top_k=top_k)
    return KBSearchResponse(
        results=[KBSearchResult(**r) for r in results]
    )


@app.post("/kb/v1/admin/cards/upsert", response_model=KBFixCardResponse)
async def upsert_card(body: KBFixCardCreateRequest) -> KBFixCardResponse:
    """Admin endpoint: upsert a Fix Card."""
    embedding = None
    try:
        embedding = embed_text(body.content)
    except Exception as exc:
        logger.warning("embedding_generation_failed", cwe_id=body.cwe_id, error=str(exc))

    card = await upsert_fix_card(
        cwe_id=body.cwe_id,
        title=body.title,
        content=body.content,
        tags=body.tags,
        source=body.source,
        embedding=embedding,
    )
    
    return KBFixCardResponse(
        id=card.id, cwe_id=card.cwe_id, title=card.title, tags=card.tags,
        summary=card.summary, fix_steps_json=card.fix_steps_json,
        content=card.content, source=card.source, approved=card.approved,
        original_finding_id=card.original_finding_id,
        usage_count=card.usage_count,
        created_at=card.created_at, updated_at=card.updated_at,
    )


def main() -> None:
    import uvicorn

    uvicorn.run(
        "kb_service.service:app",
        host="0.0.0.0",
        port=8002,
        log_level=settings.api_log_level,
        reload=True,
    )


if __name__ == "__main__":
    main()
