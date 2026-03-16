"""Optional FastAPI KB service for Fix Cards retrieval.

Endpoints:
    GET  /kb/v1/cards/{cwe_id}
    GET  /kb/v1/search?q=&topK=
    POST /kb/v1/admin/cards/upsert
"""

import os
import json
from datetime import datetime, timezone
from typing import cast, List, Dict, Any, Optional

from fastapi import FastAPI, HTTPException, Query, Request, Response, Header, Depends
from pydantic import BaseModel, Field, constr

import firebase_admin
from firebase_admin import credentials, firestore

from shared.config import get_settings
from shared.firestore_models import KBFixCardDoc
from shared.firestore_client import get_firestore_client
from shared.logging import get_logger, set_request_id, setup_logging
from shared.schemas import (
    KBFixCardCreateRequest,
    KBFixCardResponse,
    KBSearchResponse,
    KBSearchResult,
)

from kb_service.embedding import store_embeddings_from_metadata
from kb_service.store import get_fix_card, vector_search

settings = get_settings()
setup_logging(settings.api_log_level)
logger = get_logger(__name__)

app = FastAPI(title="CCV KB Service", version="0.1.0")

# ============================================================
# Security
# ============================================================
API_KEY = os.environ.get("API_KEY")

def require_api_key(x_api_key: Optional[str] = Header(None)):
    if API_KEY and x_api_key != API_KEY:
        raise HTTPException(status_code=401, detail="Unauthorized")
    return True

# ============================================================
# Option B Models
# ============================================================
class UIFindingPayload(BaseModel):
    content: constr(strip_whitespace=True, min_length=1)
    cwe_id: int
    fix_steps_json: Dict[str, Any] = Field(..., description="e.g., {'steps': [...]}")
    source: constr(strip_whitespace=True, min_length=1)  # e.g., "finding:find-xxxx"
    summary: constr(strip_whitespace=True, min_length=1)
    tags: List[constr(strip_whitespace=True, min_length=1)]
    title: constr(strip_whitespace=True, min_length=1)
    risk: constr(strip_whitespace=True, min_length=1)

class UIIngestRequest(BaseModel):
    item: UIFindingPayload
    index_display_name: Optional[str] = None
    index_description: Optional[str] = None
    overwrite: Optional[bool] = Field(
        False, description="Set True to fully overwrite the index content"
    )
    require_firestore_match: Optional[bool] = Field(
        False,
        description=(
            "If True and Firestore document is missing, returns 404. "
            "If False (default), proceeds with UI payload alone."
        ),
    )

class UIIngestResponse(BaseModel):
    ok: bool
    finding_id: str
    firestore_found: bool
    ingested_count: int
    index_id: str
    endpoint_id: str
    gcs_uri: str
    index_display_name: str
    overwrite: bool

# ============================================================
# Helpers (Option B)
# ============================================================
def _extract_finding_id(source: str) -> str:
    if ":" in source:
        return source.split(":", 1)[1].strip()
    return source.strip()

def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()

def _build_embedding_text(ui: UIFindingPayload, firestore_doc: Optional[Dict[str, Any]]) -> str:
    lines: List[str] = []
    lines.append(f"Title: {ui.title}")
    lines.append(f"Summary: {ui.summary}")
    lines.append(f"Risk: {ui.risk}")
    lines.append(f"Content: {ui.content}")
    lines.append("Fix Steps:")
    steps = []
    if isinstance(ui.fix_steps_json, dict):
        steps = ui.fix_steps_json.get("steps", [])
    for s in steps:
        lines.append(f" - {s}")
    lines.append(f"CWE ID: {ui.cwe_id}")
    if ui.tags:
        lines.append("Tags: " + ", ".join(ui.tags))

    if firestore_doc:
        try:
            compact_json = json.dumps(firestore_doc, ensure_ascii=False, separators=(",", ":"))
            lines.append("\n=== Firestore finding_analyses Document (compact) ===")
            lines.append(compact_json)
        except Exception:
            lines.append("\n=== Firestore finding_analyses Document (raw) ===")
            lines.append(str(firestore_doc))

    return "\n".join(lines).strip()


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


@app.post("/kb/v1/ingest/ui", response_model=UIIngestResponse, dependencies=[Depends(require_api_key)])
async def ingest_from_ui(req: UIIngestRequest):
    """
    Option B endpoint: Receives UI payload, fetches finding_analyses/<finding_id> from Firestore,
    combines + embeds + stores (Batch) in Vertex AI Vector Search.
    """
    try:
        ui = req.item
        finding_id = _extract_finding_id(ui.source)
        if not finding_id:
            raise HTTPException(status_code=400, detail="Invalid 'source'—unable to extract finding id.")

        # Fetch Firestore doc
        db = get_firestore_client()
        doc_ref = db.collection("finding_analyses").document(finding_id)
        doc_snap = doc_ref.get()
        firestore_found = doc_snap.exists

        if req.require_firestore_match and not firestore_found:
            raise HTTPException(
                status_code=404,
                detail=f"Firestore document 'finding_analyses/{finding_id}' not found."
            )

        firestore_data: Optional[Dict[str, Any]] = doc_snap.to_dict() if firestore_found else None

        # Combine metadata
        combined_metadata: Dict[str, Any] = {
            "finding_id": finding_id,
            "ui_payload": ui.dict(),
            "firestore_found": firestore_found,
            "firestore_data": firestore_data or {},
            "updated_at": _now_iso(),
        }

        # Build embedding text
        embedding_text = _build_embedding_text(ui, firestore_data)

        # Call Option B pipeline
        result = store_embeddings_from_metadata(
            items=[
                {
                    "id": finding_id,
                    "metadata": combined_metadata,
                    "text": embedding_text
                }
            ],
            overwrite=bool(req.overwrite),
        )

        return UIIngestResponse(
            ok=True,
            finding_id=finding_id,
            firestore_found=firestore_found,
            ingested_count=int(result.get("ingested_count", 1)),
            index_id=result.get("index_id", "unknown-index"),
            endpoint_id=result.get("endpoint_id", "unknown-endpoint"),
            gcs_uri=result.get("gcs_uri", "(not returned)"),
            index_display_name=req.index_display_name or "ccv-kb-index",
            overwrite=bool(req.overwrite),
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.exception("ingest_from_ui_failed")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/kb/v1/admin/cards/upsert", response_model=KBFixCardResponse)
async def upsert_card(body: KBFixCardCreateRequest) -> KBFixCardResponse:
    """
    Admin endpoint: upsert a Fix Card using Option B Batch ingestion.
    Note: This is a synchronous-style call wraps the batch pipeline for simplicity.
    """
    # 1. Store in Firestore (Standard practice)
    # We reuse the legacy upsert_fix_card logic for Firestore storage but skip real-time embedding if we want Option B
    # Actually, legacy upsert_fix_card might still be useful for Firestore.
    from kb_service.store import upsert_fix_card
    
    card = await upsert_fix_card(
        cwe_id=body.cwe_id,
        title=body.title,
        content=body.content,
        tags=body.tags,
        source=body.source,
        embedding=None, # We'll let the batch pipeline handle embeddings
    )

    # 2. Trigger Option B Ingestion
    try:
        store_embeddings_from_metadata(
            items=[
                {
                    "id": card.id,
                    "metadata": {
                        "cwe_id": card.cwe_id,
                        "title": card.title,
                        "source": card.source,
                        "tags": card.tags
                    },
                    "text": card.content
                }
            ],
            overwrite=False
        )
    except Exception as exc:
        logger.error("option_b_upsert_failed", error=str(exc))

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
