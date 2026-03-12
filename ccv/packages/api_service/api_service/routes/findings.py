"""Finding listing, detail, analysis, and analysis-request endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, BackgroundTasks
from google.cloud.firestore_v1 import AsyncClient

from shared.firestore_models import AuditLogDoc
from shared.logging import get_logger, get_request_id
from shared.pubsub_client import publish_analyze_finding
from shared.repositories.analysis_store import AnalysisStore
from shared.repositories.audit_store import AuditStore
from shared.repositories.finding_store import FindingStore
from shared.repositories.kb_store import KBFixCardStore
from shared.repositories.scan_store import ScanStore
from shared.schemas import (
    FindingAnalysisResponse,
    FindingListResponse,
    FindingResponse,
    KBFixCardResponse,
    KBFixCardListResponse,
)

from api_service.deps import db_session

router = APIRouter(prefix="/findings", tags=["findings"])
logger = get_logger(__name__)


# ── GET / — list findings with filters ───────────────────────────────────────


@router.get("", response_model=FindingListResponse | KBFixCardListResponse)
async def list_findings(
    scan_id: str | None = Query(None, description="Filter findings by a specific scan ID"),
    kind: str | None = Query(None, description="Set to 'kb' to list KB fix cards instead"),
    severity: str | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(500, ge=1, le=1000),
    db: AsyncClient = Depends(db_session),
) -> FindingListResponse | KBFixCardListResponse:
    """List findings with rich filtering.

    When ``kind=kb`` the request is delegated to the KB fix-card listing.
    """
    # ── KB delegation ────────────────────────────────────────────────────
    if kind == "kb":
        kb_store = KBFixCardStore(db)
        cards, total = await kb_store.list_cards(page=page, page_size=page_size)
        
        # Deduplicate by CWE ID
        unique_cards = {}
        for c in cards:
            if c.cwe_id not in unique_cards:
                unique_cards[c.cwe_id] = c
        
        return KBFixCardListResponse(
            items=[
                KBFixCardResponse(
                    id=c.id, cwe_id=c.cwe_id, title=c.title, tags=c.tags,
                    summary=c.summary, fix_steps_json=c.fix_steps_json,
                    content=c.content, source=c.source, approved=c.approved,
                    original_finding_id=c.original_finding_id,
                    usage_count=c.usage_count,
                    created_at=c.created_at, updated_at=c.updated_at,
                )
                for c in unique_cards.values()
            ],
            total=len(unique_cards),
            page=page,
            page_size=page_size,
        )

    # ── Standard finding listing ─────────────────────────────────────────
    finding_store = FindingStore(db)
    items, total = await finding_store.list_findings(
        scan_id=scan_id, severity=severity, page=page, page_size=page_size,
    )

    seen_fingerprints = set()
    unique_items = []
    for f in items:
        if f.fingerprint not in seen_fingerprints:
            unique_items.append(f)
            seen_fingerprints.add(f.fingerprint)

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
            for f in unique_items
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
        code_snippet=analysis.code_snippet,
        references_json=analysis.references_json,
        provenance_json=analysis.provenance_json,
        confidence=analysis.confidence,
        created_at=analysis.created_at, updated_at=analysis.updated_at,
    )


# ── POST /{findingId}/analysis/request — publish ANALYZE_FINDING ─────────────


@router.post("/{finding_id}/analysis/request", status_code=202)
async def request_finding_analysis(
    finding_id: str,
    background_tasks: BackgroundTasks,
    db: AsyncClient = Depends(db_session),
) -> dict:
    """Publish an ANALYZE_FINDING message to Pub/Sub for the given finding."""
    finding_store = FindingStore(db)
    audit_store = AuditStore(db)

    finding = await finding_store.get_finding(finding_id)
    if not finding:
        raise HTTPException(status_code=404, detail="Finding not found")

    # Bypass PubSub push subscriptions locally by feeding the agent task directly into FastAPI background concurrency
    try:
        from analysis_agent.agent import analyze_finding
        background_tasks.add_task(analyze_finding, finding_id)
    except ImportError:
        logger.warning("analysis_agent_not_available_for_background_task")
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


# ── POST /backfill-snippets/{scan_id} — extract real code from repo ──────────


async def _do_backfill_snippets(scan_id: str) -> None:
    """Background task: clone repo, extract snippets, update findings."""
    from shared.firestore_client import get_firestore_client
    from shared.repositories.finding_store import FindingStore
    from shared.repositories.scan_store import ScanStore
    from shared.repo_fetcher import clone_repo, cleanup_repo
    import os
    from pathlib import Path

    db = get_firestore_client()
    scan_store = ScanStore(db)
    finding_store = FindingStore(db)

    scan = await scan_store.get_scan(scan_id)
    if not scan:
        logger.error("backfill_scan_not_found", scan_id=scan_id)
        return

    # Get all findings for this scan
    findings, total = await finding_store.list_findings(scan_id=scan_id, page=1, page_size=500)
    if not findings:
        logger.info("backfill_no_findings", scan_id=scan_id)
        return

    # Only process findings that don't already have a snippet
    needs_snippet = [
        f for f in findings
        if not f.code_snippet_json or not f.code_snippet_json.get("snippet")
    ]
    if not needs_snippet:
        logger.info("backfill_all_have_snippets", scan_id=scan_id)
        return

    logger.info("backfill_starting", scan_id=scan_id, count=len(needs_snippet))

    repo_path = None
    try:
        repo_path = clone_repo(scan.repo_id, scan.branch)
        repo = Path(repo_path)

        # Pre-build filename→path index
        file_index: dict[str, Path] = {}
        for root, _, files in os.walk(repo):
            if any(skip in root for skip in (".git", "node_modules", "target", "__pycache__")):
                continue
            for fname in files:
                full = Path(root) / fname
                file_index[fname.lower()] = full

        updated = 0
        context_lines = 10

        for finding in needs_snippet:
            try:
                fp = finding.file_path
                if not fp or fp.lower() == "unknown":
                    continue

                # Try exact path match
                candidate = repo / fp
                if not candidate.is_file():
                    basename = os.path.basename(fp).lower()
                    candidate = file_index.get(basename)
                    if not candidate or not candidate.is_file():
                        continue

                content = candidate.read_text(encoding="utf-8", errors="ignore")
                lines = content.splitlines()
                target_line = finding.line or 1
                start = max(0, target_line - context_lines - 1)
                end = min(len(lines), target_line + context_lines)
                snippet_lines = lines[start:end]

                if snippet_lines:
                    rel_path = str(candidate.relative_to(repo)) if repo in candidate.parents or candidate.parent == repo else fp
                    snippet_json = {
                        "snippet": "\n".join(snippet_lines),
                        "file_path": rel_path,
                        "start_line": start + 1,
                        "highlight_lines": [target_line] if finding.line else [],
                    }
                    await finding_store.update_finding(finding.id, {
                        "code_snippet_json": snippet_json,
                    })
                    updated += 1
            except Exception:
                continue

        logger.info("backfill_done", scan_id=scan_id, updated=updated, total=len(needs_snippet))

    except Exception as exc:
        logger.error("backfill_failed", scan_id=scan_id, error=str(exc), exc_info=True)
    finally:
        if repo_path:
            cleanup_repo(repo_path)


@router.post("/backfill-snippets/{scan_id}", status_code=202)
async def backfill_snippets(
    scan_id: str,
    background_tasks: BackgroundTasks,
    db: AsyncClient = Depends(db_session),
) -> dict:
    """Extract real code snippets from the repo for all findings in a scan.

    This clones the repository, reads the actual source files, and extracts
    ±10 lines of context around each finding's reported line number.
    Runs as a background task.
    """
    scan_store = ScanStore(db)
    scan = await scan_store.get_scan(scan_id)
    if not scan:
        raise HTTPException(status_code=404, detail="Scan not found")

    background_tasks.add_task(_do_backfill_snippets, scan_id)

    logger.info("backfill_snippets_queued", scan_id=scan_id)
    return {"status": "accepted", "scan_id": scan_id, "message": "Snippet extraction started in background"}

