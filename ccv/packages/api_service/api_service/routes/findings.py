"""Finding listing, detail, analysis, and analysis-request endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from google.cloud.firestore_v1 import AsyncClient

from shared.firestore_models import AuditLogDoc
from shared.logging import get_logger, get_request_id
from shared.pubsub_client import publish_analyze_finding
from shared.repositories.analysis_store import AnalysisStore
from shared.repositories.audit_store import AuditStore
from shared.repositories.finding_store import FindingStore
from shared.repositories.kb_store import KBFixCardStore
from shared.schemas import (
    FindingAnalysisResponse,
    FindingListResponse,
    FindingResponse,
    KBFixCardResponse,
)

from api_service.deps import db_session

router = APIRouter(prefix="/findings", tags=["findings"])
logger = get_logger(__name__)


# ── GET / — list findings with filters ───────────────────────────────────────


@router.get("", response_model=FindingListResponse)
async def list_findings(
    scan_id: str | None = Query(None, description="Filter findings by a specific scan ID"),
    kind: str | None = Query(None, description="Set to 'kb' to list KB fix cards instead"),
    severity: str | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    db: AsyncClient = Depends(db_session),
) -> FindingListResponse | dict:
    """List findings with rich filtering.

    When ``kind=kb`` the request is delegated to the KB fix-card listing.
    """
    # ── KB delegation ────────────────────────────────────────────────────
    if kind == "kb":
        kb_store = KBFixCardStore(db)
        cards, total = await kb_store.list_cards(page=page, page_size=page_size)
        return {
            "items": [
                KBFixCardResponse(
                    id=c.id, cwe_id=c.cwe_id, title=c.title, tags=c.tags,
                    summary=c.summary, fix_steps_json=c.fix_steps_json,
                    content=c.content, source=c.source, approved=c.approved,
                    original_finding_id=c.original_finding_id,
                    usage_count=c.usage_count,
                    created_at=c.created_at, updated_at=c.updated_at,
                ).model_dump(mode="json")
                for c in cards
            ],
            "total": total,
            "page": page,
            "page_size": page_size,
        }

    # ── Standard finding listing ─────────────────────────────────────────
    finding_store = FindingStore(db)
    items, total = await finding_store.list_findings(
        scan_id=scan_id, severity=severity, page=page, page_size=page_size,
    )

    return FindingListResponse(
        items=[
            FindingResponse(
                id=f.id, scan_id=f.scan_id, cwe_id=f.cwe_id, severity=f.severity,
                title=f.title, file_path=f.file_path, line=f.line,
                fingerprint=f.fingerprint,
                enrichment_summary=f.enrichment_summary,
                enrichment_confidence=f.enrichment_confidence,
                raw_source_json=f.raw_source_json,
                code_snippet_json=f.code_snippet_json,
                created_at=f.created_at,
            )
            for f in items
        ],
        total=total,
        page=page,
        page_size=page_size,
    )


# ── GET /{findingId} — single finding detail ─────────────────────────────────


@router.get("/{finding_id}", response_model=FindingResponse)
async def get_finding(
    finding_id: str,
    db: AsyncClient = Depends(db_session),
) -> FindingResponse:
    """Get a single finding by id."""
    finding_store = FindingStore(db)
    finding = await finding_store.get_finding(finding_id)
    if not finding:
        raise HTTPException(status_code=404, detail="Finding not found")
    return FindingResponse(
        id=finding.id, scan_id=finding.scan_id, cwe_id=finding.cwe_id,
        severity=finding.severity, title=finding.title,
        file_path=finding.file_path, line=finding.line,
        fingerprint=finding.fingerprint,
        enrichment_summary=finding.enrichment_summary,
        enrichment_confidence=finding.enrichment_confidence,
        raw_source_json=finding.raw_source_json,
        code_snippet_json=finding.code_snippet_json,
        created_at=finding.created_at,
    )


# ── GET /{findingId}/analysis — get analysis for a finding ───────────────────


@router.get("/{finding_id}/analysis", response_model=FindingAnalysisResponse)
async def get_finding_analysis(
    finding_id: str,
    db: AsyncClient = Depends(db_session),
) -> FindingAnalysisResponse:
    """Return the AI analysis for a specific finding."""
    analysis_store = AnalysisStore(db)
    analysis = await analysis_store.get_by_finding_id(finding_id)
    if not analysis:
        raise HTTPException(status_code=404, detail="Analysis not found for this finding")
    return FindingAnalysisResponse(
        id=analysis.id, finding_id=analysis.finding_id,
        model_name=analysis.model_name, model_version=analysis.model_version,
        root_cause=analysis.root_cause, risk=analysis.risk,
        fix_guidance=analysis.fix_guidance,
        references_json=analysis.references_json,
        provenance_json=analysis.provenance_json,
        confidence=analysis.confidence,
        created_at=analysis.created_at, updated_at=analysis.updated_at,
    )


# ── POST /{findingId}/analysis/request — publish ANALYZE_FINDING ─────────────


@router.post("/{finding_id}/analysis/request", status_code=202)
async def request_finding_analysis(
    finding_id: str,
    db: AsyncClient = Depends(db_session),
) -> dict:
    """Publish an ANALYZE_FINDING message to Pub/Sub for the given finding."""
    finding_store = FindingStore(db)
    audit_store = AuditStore(db)

    finding = await finding_store.get_finding(finding_id)
    if not finding:
        raise HTTPException(status_code=404, detail="Finding not found")

    publish_analyze_finding(finding_id)

    await audit_store.log_entry(AuditLogDoc(
        request_id=get_request_id(),
        actor="api",
        action="request_finding_analysis",
        entity_type="finding",
        entity_id=finding_id,
        status="published",
    ))

    logger.info("analysis_requested", finding_id=finding_id)
    return {"status": "accepted", "finding_id": finding_id}
