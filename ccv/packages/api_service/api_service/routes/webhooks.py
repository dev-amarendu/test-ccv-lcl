"""Bitbucket PR webhook endpoint (optional, controlled by env flag)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from google.cloud.firestore_v1 import AsyncClient

from shared.config import Settings
from shared.firestore_models import AuditLogDoc
from shared.logging import get_logger, get_request_id
from shared.repositories.audit_store import AuditStore
from shared.schemas import BitbucketPRWebhookPayload

from api_service.deps import db_session, settings

router = APIRouter(prefix="/webhooks", tags=["webhooks"])
logger = get_logger(__name__)


@router.post("/bitbucket/pullrequest", status_code=202)
async def bitbucket_pr_webhook(
    payload: BitbucketPRWebhookPayload,
    db: AsyncClient = Depends(db_session),
    cfg: Settings = Depends(settings),
) -> dict:
    """Handle an incoming Bitbucket pull-request webhook."""
    if not cfg.bitbucket_enabled:
        raise HTTPException(status_code=404, detail="Bitbucket webhooks are disabled")

    pr_data = payload.pullrequest
    repo_data = payload.repository

    pr_number = pr_data.get("id", 0)
    source_branch = pr_data.get("source", {}).get("branch", {}).get("name", "unknown")
    target_branch = pr_data.get("destination", {}).get("branch", {}).get("name", "main")
    commit_sha = pr_data.get("source", {}).get("commit", {}).get("hash", "")
    repo_name = repo_data.get("full_name", "unknown")

    logger.info(
        "bitbucket_webhook_received",
        pr_number=pr_number,
        repo=repo_name,
        source=source_branch,
        target=target_branch,
        commit_sha=commit_sha,
    )

    # 1. Lookup Repo (to get ID)
    from shared.repositories.repos import RepoStore
    repo_store = RepoStore(db)
    # TODO: We need a way to look up repo by name/url, for now iterating
    # Ideally RepoDoc should have a `external_url` or `full_name` index
    # For MVP, we assume the user has configured the repo with the same name
    
    # Simple search by name match
    # In a real system, you'd have a `find_by_external_name` method
    target_repo = None
    all_repos = await repo_store.list_repos()
    for r in all_repos:
        if r.name in repo_name or repo_name in r.name:
            target_repo = r
            break
            
    scan_id = None
    if target_repo:
        # 2. Trigger Scan if merged to main
        if target_branch == "main" and commit_sha:
            from shared.repositories.scan_store import ScanStore
            from shared.firestore_models import ScanDoc, ScanStatus, TriggerType
            from shared.utils import generate_uuid
            from shared.pubsub_client import publish_run_scan
            
            scan_store = ScanStore(db)
            scan_id = str(generate_uuid())
            
            scan = ScanDoc(
                id=scan_id,
                repo_id=target_repo.id,
                branch=target_branch,
                commit_sha=commit_sha,
                trigger_type=TriggerType.WEBHOOK,
                status=ScanStatus.QUEUED,
            )
            await scan_store.create_scan(scan)
            publish_run_scan(scan_id)
            logger.info("webhook_triggered_scan", scan_id=scan_id, repo=target_repo.name)

    audit_store = AuditStore(db)
    await audit_store.log_entry(AuditLogDoc(
        request_id=get_request_id(),
        actor="bitbucket_webhook",
        action="pr_webhook_received",
        entity_type="pull_request",
        entity_id=str(pr_number),
        status="accepted",
        details_json={
            "repo": repo_name,
            "source": source_branch,
            "target": target_branch,
            "commit_sha": commit_sha,
            "triggered_scan_id": scan_id
        },
    ))

    return {
        "status": "accepted",
        "message": f"PR #{pr_number} webhook received for {repo_name}. Scan triggered: {scan_id}",
    }
