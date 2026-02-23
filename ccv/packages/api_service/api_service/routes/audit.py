"""Audit log listing endpoint."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from google.cloud.firestore_v1 import AsyncClient

from shared.logging import get_logger
from shared.repositories.audit_store import AuditStore
from shared.schemas import AuditListResponse, AuditLogResponse

from api_service.deps import db_session

router = APIRouter(prefix="/audit", tags=["audit"])
logger = get_logger(__name__)


@router.get("", response_model=AuditListResponse)
async def list_audit_logs(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    db: AsyncClient = Depends(db_session),
) -> AuditListResponse:
    """List audit log entries with pagination (newest first)."""
    store = AuditStore(db)
    items, total = await store.list_logs(page=page, page_size=page_size)
    return AuditListResponse(
        items=[
            AuditLogResponse(
                id=a.id, request_id=a.request_id, actor=a.actor,
                action=a.action, entity_type=a.entity_type,
                entity_id=a.entity_id, status=a.status,
                details_json=a.details_json,
                created_at=a.created_at,
            )
            for a in items
        ],
        total=total,
        page=page,
        page_size=page_size,
    )
