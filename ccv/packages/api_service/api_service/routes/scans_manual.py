"""Manual scan management and Veracode sync trigger endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from google.cloud.firestore_v1 import AsyncClient

from shared.firestore_models import AuditLogDoc, ScanDoc, ScanStatus, TriggerType
from shared.logging import get_logger, get_request_id
from shared.pubsub_client import publish_run_scan, publish_sync_veracode
from shared.repositories.audit_store import AuditStore
from shared.repositories.finding_store import FindingStore
from shared.repositories.scan_store import ScanStore
from shared.schemas import (
    FindingListResponse,
    FindingResponse,
    ManualScanRequest,
    ScanListResponse,
    ScanResponse,
    ScanStatusEnum,
    TriggerTypeEnum,
)
from shared.utils import generate_uuid

from api_service.deps import db_session

router = APIRouter(prefix="/scans/manual", tags=["scans"])
logger = get_logger(__name__)


# ── POST / — trigger a manual scan ───────────────────────────────────────────


@router.post("", response_model=ScanResponse, status_code=201)
async def trigger_manual_scan(
    body: ManualScanRequest,
    db: AsyncClient = Depends(db_session),
) -> ScanResponse:
    """Create a new scan with trigger_type=MANUAL and publish RUN_SCAN to Pub/Sub."""
    scan_store = ScanStore(db)
    audit_store = AuditStore(db)

    scan = ScanDoc(
        id=str(generate_uuid()),
        repo_id=str(body.repo_id),
        branch=body.branch,
        commit_sha=body.commit_sha,
        trigger_type=TriggerType.MANUAL,
        status=ScanStatus.QUEUED,
    )
    await scan_store.create_scan(scan)

    # Publish to Pub/Sub instead of creating a Job row
    publish_run_scan(scan.id)

    await audit_store.log_entry(AuditLogDoc(
        request_id=get_request_id(),
        actor="api",
        action="trigger_manual_scan",
        entity_type="scan",
        entity_id=scan.id,
        status="created",
    ))

    logger.info("manual_scan_triggered", scan_id=scan.id)
    return ScanResponse(
        id=scan.id, repo_id=scan.repo_id, branch=scan.branch,
        commit_sha=scan.commit_sha, trigger_type=TriggerTypeEnum(scan.trigger_type.value),
        status=ScanStatusEnum(scan.status.value),
        created_at=scan.created_at, updated_at=scan.updated_at,
    )


# ── GET / — list ALL scans with filters ──────────────────────────────────────


@router.get("", response_model=ScanListResponse)
async def list_scans(
    repo_id: str | None = Query(None, alias="repoId"),
    status: ScanStatusEnum | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    db: AsyncClient = Depends(db_session),
) -> ScanListResponse:
    """List scans with optional filters."""
    scan_store = ScanStore(db)
    fs_status = ScanStatus(status.value) if status else None
    items, total = await scan_store.list_scans(
        repo_id=repo_id, status=fs_status, page=page, page_size=page_size,
    )
    return ScanListResponse(
        items=[
            ScanResponse(
                id=s.id, repo_id=s.repo_id, pr_id=s.pr_id, branch=s.branch,
                commit_sha=s.commit_sha,
                trigger_type=TriggerTypeEnum(s.trigger_type.value),
                status=ScanStatusEnum(s.status.value),
                external_build_id=s.external_build_id,
                external_app_id=s.external_app_id,
                started_at=s.started_at, finished_at=s.finished_at,
                error_message=s.error_message,
                created_at=s.created_at, updated_at=s.updated_at,
            )
            for s in items
        ],
        total=total,
        page=page,
        page_size=page_size,
    )


# ── GET /{scanId} — single scan detail ───────────────────────────────────────


@router.get("/{scan_id}", response_model=ScanResponse)
async def get_scan(
    scan_id: str,
    db: AsyncClient = Depends(db_session),
) -> ScanResponse:
    """Get a scan by its ID."""
    scan_store = ScanStore(db)
    scan = await scan_store.get_scan(scan_id)
    if not scan:
        raise HTTPException(status_code=404, detail="Scan not found")
    return ScanResponse(
        id=scan.id, repo_id=scan.repo_id, pr_id=scan.pr_id, branch=scan.branch,
        commit_sha=scan.commit_sha,
        trigger_type=TriggerTypeEnum(scan.trigger_type.value),
        status=ScanStatusEnum(scan.status.value),
        external_build_id=scan.external_build_id,
        external_app_id=scan.external_app_id,
        started_at=scan.started_at, finished_at=scan.finished_at,
        error_message=scan.error_message,
        created_at=scan.created_at, updated_at=scan.updated_at,
    )


# ── POST /{scanId}/rerun — re-run a previous scan ────────────────────────────


@router.post("/{scan_id}/rerun", response_model=ScanResponse, status_code=201)
async def rerun_scan(
    scan_id: str,
    db: AsyncClient = Depends(db_session),
) -> ScanResponse:
    """Re-run an existing scan."""
    scan_store = ScanStore(db)
    audit_store = AuditStore(db)

    original = await scan_store.get_scan(scan_id)
    if not original:
        raise HTTPException(status_code=404, detail="Original scan not found")

    new_scan = ScanDoc(
        id=str(generate_uuid()),
        repo_id=original.repo_id,
        branch=original.branch,
        commit_sha=original.commit_sha,
        trigger_type=TriggerType.MANUAL,
        status=ScanStatus.QUEUED,
    )
    await scan_store.create_scan(new_scan)

    publish_run_scan(new_scan.id)

    await audit_store.log_entry(AuditLogDoc(
        request_id=get_request_id(),
        actor="api",
        action="rerun_scan",
        entity_type="scan",
        entity_id=new_scan.id,
        status="created",
        details_json={"rerun_of": scan_id},
    ))

    logger.info("scan_rerun", new_scan_id=new_scan.id, original_scan_id=scan_id)
    return ScanResponse(
        id=new_scan.id, repo_id=new_scan.repo_id, branch=new_scan.branch,
        commit_sha=new_scan.commit_sha,
        trigger_type=TriggerTypeEnum(new_scan.trigger_type.value),
        status=ScanStatusEnum(new_scan.status.value),
        created_at=new_scan.created_at, updated_at=new_scan.updated_at,
    )


# ── POST /{scanId}/cancel — cancel a long-running scan ───────────────────────


@router.post("/{scan_id}/cancel", response_model=ScanResponse, status_code=200)
async def cancel_scan(
    scan_id: str,
    db: AsyncClient = Depends(db_session),
) -> ScanResponse:
    """Mark an active scan as CANCELLED to gracefully interrupt it."""
    scan_store = ScanStore(db)
    audit_store = AuditStore(db)

    scan = await scan_store.get_scan(scan_id)
    if not scan:
        raise HTTPException(status_code=404, detail="Scan not found")

    if scan.status in (ScanStatus.COMPLETED, ScanStatus.FAILED, ScanStatus.CANCELLED):
        raise HTTPException(status_code=400, detail=f"Cannot cancel scan in {scan.status.value} state")

    from datetime import datetime, timezone
    await scan_store.update_scan(scan_id, {
        "status": ScanStatus.CANCELLED,
        "finished_at": datetime.now(timezone.utc),
        "error_message": "Scan cancelled by operator via API",
    })

    await audit_store.log_entry(AuditLogDoc(
        request_id=get_request_id(),
        actor="api",
        action="cancel_scan",
        entity_type="scan",
        entity_id=scan.id,
        status="cancelled",
    ))

    logger.info("scan_cancelled", scan_id=scan.id)
    
    # Refresh to return updated object
    scan = await scan_store.get_scan(scan_id)
    return ScanResponse(
        id=scan.id, repo_id=scan.repo_id, branch=scan.branch,
        commit_sha=scan.commit_sha,
        trigger_type=TriggerTypeEnum(scan.trigger_type.value),
        status=ScanStatusEnum(scan.status.value),
        created_at=scan.created_at, updated_at=scan.updated_at,
    )


# ── GET /{scanId}/findings — findings for a specific scan ────────────────────


@router.get("/{scan_id}/findings", response_model=FindingListResponse)
async def list_scan_findings(
    scan_id: str,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    db: AsyncClient = Depends(db_session),
) -> FindingListResponse:
    """List findings belonging to a specific scan (paginated)."""
    scan_store = ScanStore(db)
    finding_store = FindingStore(db)

    scan = await scan_store.get_scan(scan_id)
    if not scan:
        raise HTTPException(status_code=404, detail="Scan not found")

    items, total = await finding_store.list_findings(scan_id=scan_id, page=page, page_size=page_size)
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


# ── POST /sync — trigger a Veracode sync via Pub/Sub ─────────────────────────


@router.post("/sync", status_code=202)
async def trigger_veracode_sync(
    db: AsyncClient = Depends(db_session),
) -> dict:
    """Manually trigger a Veracode sync via Pub/Sub."""
    audit_store = AuditStore(db)

    publish_sync_veracode()

    await audit_store.log_entry(AuditLogDoc(
        request_id=get_request_id(),
        actor="api",
        action="trigger_veracode_sync",
        entity_type="job",
        entity_id="pubsub",
        status="published",
    ))

    logger.info("veracode_sync_triggered")
    return {"status": "accepted"}
