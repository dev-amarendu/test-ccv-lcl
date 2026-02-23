"""KB fix-card endpoints nested under /findings/kb."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from google.cloud.firestore_v1 import AsyncClient

from shared.firestore_models import AuditLogDoc, KBFixCardDoc
from shared.logging import get_logger, get_request_id
from shared.repositories.audit_store import AuditStore
from shared.repositories.kb_store import KBFixCardStore
from shared.schemas import (
    KBFixCardCreateRequest,
    KBFixCardResponse,
    KBFixCardUpdateRequest,
)
from shared.utils import content_hash, generate_uuid

from api_service.deps import db_session

router = APIRouter(prefix="/findings/kb", tags=["kb"])
logger = get_logger(__name__)


@router.get("", response_model=list[KBFixCardResponse])
async def list_kb_fix_cards(
    db: AsyncClient = Depends(db_session),
) -> list[KBFixCardResponse]:
    """List all KB fix cards."""
    store = KBFixCardStore(db)
    cards, _ = await store.list_cards(page=1, page_size=200)
    return [
        KBFixCardResponse(
            id=c.id, cwe_id=c.cwe_id, title=c.title, tags=c.tags,
            summary=c.summary, fix_steps_json=c.fix_steps_json,
            content=c.content, source=c.source, approved=c.approved,
            original_finding_id=c.original_finding_id,
            usage_count=c.usage_count,
            created_at=c.created_at, updated_at=c.updated_at,
        )
        for c in cards
    ]


@router.post("", response_model=KBFixCardResponse, status_code=201)
async def create_kb_fix_card(
    body: KBFixCardCreateRequest,
    db: AsyncClient = Depends(db_session),
) -> KBFixCardResponse:
    """Create a new KB fix card."""
    store = KBFixCardStore(db)
    audit_store = AuditStore(db)

    card = KBFixCardDoc(
        id=str(generate_uuid()),
        cwe_id=body.cwe_id,
        title=body.title,
        tags=body.tags,
        summary=body.summary,
        fix_steps_json=body.fix_steps_json,
        content=body.content,
        source=body.source,
        content_hash=content_hash(body.content),
        original_finding_id=str(body.original_finding_id) if body.original_finding_id else None,
        approved=True,
    )
    await store.upsert(card)

    await audit_store.log_entry(AuditLogDoc(
        request_id=get_request_id(),
        actor="api",
        action="create_kb_fix_card",
        entity_type="kb_fix_card",
        entity_id=card.id,
        status="created",
    ))

    logger.info("kb_fix_card_created", card_id=card.id, cwe_id=body.cwe_id)
    return KBFixCardResponse(
        id=card.id, cwe_id=card.cwe_id, title=card.title, tags=card.tags,
        summary=card.summary, fix_steps_json=card.fix_steps_json,
        content=card.content, source=card.source, approved=card.approved,
        original_finding_id=card.original_finding_id,
        usage_count=card.usage_count,
        created_at=card.created_at, updated_at=card.updated_at,
    )


@router.get("/{kb_id}", response_model=KBFixCardResponse)
async def get_kb_fix_card(
    kb_id: str,
    db: AsyncClient = Depends(db_session),
) -> KBFixCardResponse:
    """Get a single KB fix card."""
    store = KBFixCardStore(db)
    card = await store.get_by_id(kb_id)
    if not card:
        raise HTTPException(status_code=404, detail="KB fix card not found")
    return KBFixCardResponse(
        id=card.id, cwe_id=card.cwe_id, title=card.title, tags=card.tags,
        summary=card.summary, fix_steps_json=card.fix_steps_json,
        content=card.content, source=card.source, approved=card.approved,
        original_finding_id=card.original_finding_id,
        usage_count=card.usage_count,
        created_at=card.created_at, updated_at=card.updated_at,
    )


@router.patch("/{kb_id}", response_model=KBFixCardResponse)
async def update_kb_fix_card(
    kb_id: str,
    body: KBFixCardUpdateRequest,
    db: AsyncClient = Depends(db_session),
) -> KBFixCardResponse:
    """Partially update a KB fix card."""
    store = KBFixCardStore(db)
    audit_store = AuditStore(db)

    card = await store.get_by_id(kb_id)
    if not card:
        raise HTTPException(status_code=404, detail="KB fix card not found")

    update_data = body.model_dump(exclude_unset=True)

    # Re-hash content if it changed
    if "content" in update_data:
        update_data["content_hash"] = content_hash(update_data["content"])

    await store.update_card(kb_id, update_data)

    await audit_store.log_entry(AuditLogDoc(
        request_id=get_request_id(),
        actor="api",
        action="update_kb_fix_card",
        entity_type="kb_fix_card",
        entity_id=kb_id,
        status="updated",
        details_json=update_data,
    ))

    # Re-fetch updated card
    updated = await store.get_by_id(kb_id)
    logger.info("kb_fix_card_updated", card_id=kb_id)
    return KBFixCardResponse(
        id=updated.id, cwe_id=updated.cwe_id, title=updated.title, tags=updated.tags,
        summary=updated.summary, fix_steps_json=updated.fix_steps_json,
        content=updated.content, source=updated.source, approved=updated.approved,
        original_finding_id=updated.original_finding_id,
        usage_count=updated.usage_count,
        created_at=updated.created_at, updated_at=updated.updated_at,
    )
