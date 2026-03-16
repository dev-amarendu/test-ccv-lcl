# api.py
import os
import json
from typing import List, Dict, Any, Optional

from fastapi import FastAPI, Header, HTTPException, Depends
from pydantic import BaseModel, Field, constr
from datetime import datetime, timezone

# Firestore (for fetching finding_analyses/<id>)
import firebase_admin
from firebase_admin import credentials, firestore

# Your embedding pipeline
from embedding import (
    store_embeddings_from_metadata,  # we'll return a rich dict from this (see changes below)
    _settings,                       # for defaults (index name/description, region, etc.)
)

# ============================================================
# Security
# ============================================================
API_KEY = os.environ.get("API_KEY")  # optional

def require_api_key(x_api_key: Optional[str] = Header(None)):
    if API_KEY and x_api_key != API_KEY:
        raise HTTPException(status_code=401, detail="Unauthorized")
    return True

# ============================================================
# Firestore init (service account key or default creds)
# ============================================================
_firestore_client_cached: Optional[firestore.Client] = None

def get_firestore_client() -> firestore.Client:
    global _firestore_client_cached
    if _firestore_client_cached:
        return _firestore_client_cached

    # Use SERVICE_ACCOUNT_KEY_PATH if present; else try default app
    sa_path = os.environ.get("SERVICE_ACCOUNT_KEY_PATH")
    if not firebase_admin._apps:
        if sa_path and os.path.exists(sa_path):
            cred = credentials.Certificate(sa_path)
            firebase_admin.initialize_app(cred)
        else:
            # Fall back to Application Default Credentials, if available
            firebase_admin.initialize_app()

    _firestore_client_cached = firestore.client()
    return _firestore_client_cached

# ============================================================
# FastAPI app
# ============================================================
app = FastAPI(
    title="Findings KB API",
    version="0.0.0.0",
    description=(
        "Ingests UI-triggered findings by combining UI payload with Firestore "
        "finding_analyses/<id> and stores it in Vertex AI Vector Search."
    ),
)

# ============================================================
# Models: UI payload & request/response
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
# Helpers
# ============================================================
def _extract_finding_id(source: str) -> str:
    """
    Examples:
      "finding:find-0000-0001-4000-8000-000000000001" -> "find-0000-0001-4000-8000-000000000001"
      "find-0000-0001-4000-8000-000000000001"         -> "find-0000-0001-4000-8000-000000000001"
    """
    if ":" in source:
        return source.split(":", 1)[1].strip()
    return source.strip()

def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()

def _build_embedding_text(ui: UIFindingPayload, firestore_doc: Optional[Dict[str, Any]]) -> str:
    """
    Creates a clean, search-friendly text for embeddings, combining UI + Firestore.
    JSON-ish parts are stringified compactly to avoid huge tokens.
    """
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

    # Append a compact Firestore snapshot
    if firestore_doc:
        try:
            compact_json = json.dumps(firestore_doc, ensure_ascii=False, separators=(",", ":"))
            lines.append("\n=== Firestore finding_analyses Document (compact) ===")
            lines.append(compact_json)
        except Exception:
            # Fallback to str if any serialization issues
            lines.append("\n=== Firestore finding_analyses Document (raw) ===")
            lines.append(str(firestore_doc))

    return "\n".join(lines).strip()

# ============================================================
# Endpoint: UI-triggered ingestion
# ============================================================
@app.post("/api/findings/kb/ui", response_model=UIIngestResponse, dependencies=[Depends(require_api_key)])
def ingest_from_ui(req: UIIngestRequest):
    """
    Receives UI payload, fetches finding_analyses/<finding_id> from Firestore,
    combines + embeds + stores in Vertex AI Vector Search.
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

        # Call your pipeline (returns dict with rich info — see embedding1.py changes below)
        index_display_name = req.index_display_name or _settings.vector_search_index_display_name
        index_description = req.index_description or _settings.vector_search_index_description
        overwrite = bool(req.overwrite)

        result = store_embeddings_from_metadata(
            items=[
                {
                    "id": finding_id,
                    "metadata": combined_metadata,
                    "text": embedding_text
                }
            ],
            index_display_name=index_display_name,
            index_description=index_description,
            overwrite=overwrite,
        )

        # Backward-compat: if pipeline returns endpoint object vs dict
        if isinstance(result, dict):
            return UIIngestResponse(
                ok=True,
                finding_id=finding_id,
                firestore_found=firestore_found,
                ingested_count=int(result.get("ingested_count", 1)),
                index_id=result.get("index_id", "unknown-index"),
                endpoint_id=result.get("endpoint_id", "unknown-endpoint"),
                gcs_uri=result.get("gcs_uri", "(not returned)"),
                index_display_name=index_display_name,
                overwrite=overwrite,
            )
        else:
            # Older return type (endpoint object). Populate best-effort.
            endpoint_id = getattr(result, "name", "unknown-endpoint")
            return UIIngestResponse(
                ok=True,
                finding_id=finding_id,
                firestore_found=firestore_found,
                ingested_count=1,
                index_id=endpoint_id,
                endpoint_id=endpoint_id,
                gcs_uri="(see server logs)",
                index_display_name=index_display_name,
                overwrite=overwrite,
            )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ============================================================
# Health check
# ============================================================
@app.get("/healthz")
def healthz():
    return {"ok": True}