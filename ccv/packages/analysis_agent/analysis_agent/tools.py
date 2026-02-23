"""ADK Function Tools for the CCV Analysis Agent.

Each function is passed to the ADK Agent's ``tools=[...]`` list.
ADK auto-wraps plain Python functions as FunctionTools.

Tools use **synchronous** I/O because ADK executes tool functions
within its own async event-loop; sync functions avoid nested-loop issues.
"""

from __future__ import annotations

import httpx

from google.cloud import firestore

from shared.config import get_settings
from shared.logging import get_logger

logger = get_logger(__name__)

KB_SERVICE_URL = "http://localhost:8002"


def lookup_kb_fix_card(cwe_id: int) -> dict:
    """Look up a Knowledge Base Fix Card for a given CWE identifier.

    Searches the CCV knowledge base for remediation guidance matching
    a Common Weakness Enumeration (CWE) ID.

    Args:
        cwe_id: The numeric CWE identifier (e.g. 79 for XSS,
                89 for SQL Injection, 502 for Deserialization).

    Returns:
        dict with keys:
            status: 'found' if a fix card exists, 'not_found' otherwise.
            cwe_id: The CWE identifier queried.
            content: The fix card remediation text (only when status='found').
            source: Where the card came from ('kb_service' or 'firestore').
    """
    # ── Try KB micro-service API first ────────────────────────────────────
    try:
        with httpx.Client(timeout=5) as client:
            resp = client.get(f"{KB_SERVICE_URL}/kb/v1/cards/{cwe_id}")
        if resp.status_code == 200:
            data = resp.json()
            return {
                "status": "found",
                "cwe_id": cwe_id,
                "content": data.get("content", ""),
                "source": "kb_service",
            }
    except Exception:
        logger.debug("kb_service_unavailable_for_tool", cwe_id=cwe_id)

    # ── Fallback: direct Firestore query (sync client) ────────────────────
    try:
        settings = get_settings()
        db = firestore.Client(
            project=settings.firestore_project_id,
            database=settings.firestore_database,
        )
        docs = db.collection("kb_fix_cards").where("cwe_id", "==", cwe_id).limit(1).get()
        for doc in docs:
            data = doc.to_dict()
            return {
                "status": "found",
                "cwe_id": cwe_id,
                "content": data.get("content", ""),
                "source": "firestore",
            }
    except Exception:
        logger.warning("kb_firestore_fallback_failed_in_tool", cwe_id=cwe_id, exc_info=True)

    return {
        "status": "not_found",
        "cwe_id": cwe_id,
        "message": f"No fix card found for CWE-{cwe_id}",
    }
