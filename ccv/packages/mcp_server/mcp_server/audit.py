"""MCP audit logging — writes to Firestore audit_logs collection."""

from __future__ import annotations

import uuid

from shared.firestore_client import get_firestore_client
from shared.firestore_models import AuditLogDoc
from shared.logging import get_logger
from shared.repositories.audit_store import AuditStore
from shared.schemas import MCPCallRequest, MCPCallResponse

logger = get_logger(__name__)


async def log_mcp_call(request_id: str, req: MCPCallRequest, resp: MCPCallResponse) -> None:
    """Persist an audit log document for the MCP call."""
    try:
        db = get_firestore_client()
        store = AuditStore(db)
        
        await store.log_entry(AuditLogDoc(
            id=str(uuid.uuid4()),  # Audit logs usually just need unique ID
            request_id=request_id,
            actor=req.caller or "unknown",
            action=f"mcp.call.{req.tool_name}",
            entity_type="mcp_tool",
            entity_id=req.tool_name,
            status="ok" if resp.ok else "error",
            details_json={
                "params_keys": list(req.params.keys()),
                "latency_ms": resp.latency_ms,
                "error": resp.error,
            },
        ))
    except Exception:
        # Audit logging must never break the main flow
        logger.warning("audit_log_write_failed", request_id=request_id, exc_info=True)
