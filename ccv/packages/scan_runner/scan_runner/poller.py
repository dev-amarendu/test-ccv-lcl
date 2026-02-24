"""Periodic Veracode scan poller.

Usage (push-based via Pub/Sub):
    Triggered by Cloud Scheduler → Pub/Sub → /pubsub/sync-veracode endpoint

Legacy usage (can still be run standalone for debug):
    python -m scan_runner.poller
"""

from __future__ import annotations

import asyncio
import uuid
from datetime import datetime, timezone

from shared.config import get_settings
from shared.firestore_client import get_firestore_client
from shared.firestore_models import ScanDoc, ScanStatus, TriggerType
from shared.logging import get_logger, set_request_id
from shared.repositories.finding_store import FindingStore
from shared.repositories.repos import RepoStore
from shared.repositories.scan_store import ScanStore
from shared.utils import generate_uuid

from scan_runner.enqueue_analysis import enqueue_analysis_jobs
from scan_runner.normalize import normalize_findings
from scan_runner.veracode_sync_api import get_sync_state, update_sync_state
from scan_runner.veracode_upload_api import MCPClient

logger = get_logger(__name__)


async def run_sync_once() -> int:
    """Execute a single sync cycle. Returns the number of new scans processed."""
    rid = uuid.uuid4().hex[:16]
    set_request_id(rid)
    logger.info("veracode_sync_start")

    settings = get_settings()
    db = get_firestore_client()
    mcp = MCPClient()

    scan_store = ScanStore(db)
    repo_store = RepoStore(db)
    finding_store = FindingStore(db)

    app_id = settings.veracode_app_id
    if not app_id:
        logger.warning("veracode_sync_skip", msg="VERACODE_APP_ID not configured")
        return 0

    # Read current sync state
    sync_state = await get_sync_state()
    last_synced_at = sync_state.last_synced_at
    last_seen_build_id = sync_state.last_seen_build_id

    list_params: dict[str, str] = {"app_id": app_id}
    if last_synced_at:
        list_params["since_timestamp"] = last_synced_at.isoformat()
    if last_seen_build_id:
        list_params["since_build_id"] = last_seen_build_id

    try:
        scan_list_result = await mcp.call_tool(
            "veracode.list_recent_scans", list_params, caller="veracode_poller",
        )
    except Exception as exc:
        logger.error("veracode_sync_list_failed", error=str(exc))
        return 0

    scans = scan_list_result.get("scans", [])
    if not scans:
        logger.info("veracode_sync_no_new_scans")
        return 0

    # Look up a default repo
    repo = await repo_store.get_connected_repo()
    if repo is None:
        all_repos = await repo_store.list_repos()
        repo = all_repos[0] if all_repos else None

    if repo is None:
        logger.error("veracode_sync_no_repo", msg="No repo found to associate scans with")
        return 0

    processed = 0
    newest_build_id: str | None = None
    now = datetime.now(timezone.utc)

    for scan_summary in scans:
        build_id = scan_summary.get("build_id", "")
        status = scan_summary.get("status", "").lower()

        if not build_id:
            continue

        if status not in ("results ready",):
            logger.info("veracode_sync_skip_build", build_id=build_id, status=status)
            continue

        # Check if we already have this scan
        existing = await scan_store.get_by_external_build_id(build_id)
        if existing:
            logger.info("veracode_sync_already_exists", build_id=build_id)
            newest_build_id = build_id
            continue

        # Create scan doc
        scan_id = str(generate_uuid())
        scan = ScanDoc(
            id=scan_id,
            repo_id=repo.id,
            branch=repo.default_branch,
            trigger_type=TriggerType.VERACODE_SYNC,
            status=ScanStatus.RUNNING,
            external_build_id=build_id,
            external_app_id=app_id,
            started_at=now,
        )
        await scan_store.create_scan(scan)
        logger.info("veracode_sync_scan_created", scan_id=scan_id, build_id=build_id)

        # Fetch findings via MCP
        try:
            results = await mcp.call_tool(
                "veracode.get_final_results", {"app_id": app_id}, caller="veracode_poller",
            )
        except Exception as exc:
            logger.error("veracode_sync_findings_failed", build_id=build_id, error=str(exc))
            await scan_store.update_scan(scan_id, {
                "status": ScanStatus.FAILED.value,
                "finished_at": datetime.now(timezone.utc),
                "error_message": f"Failed to fetch findings: {exc}",
            })
            continue

        # Persist raw results and normalize via the new normalizer worker.
        # This writes a veracode_raw_reports doc (with sca uploaded to GCS if large)
        # and creates normalized FindingDoc entries in the `findings` collection.
        from scan_runner.normalizer import normalize_and_store

        findings = await normalize_and_store(scan_id, results)

        # Enqueue ANALYZE_FINDING messages for created findings
        await enqueue_analysis_jobs(scan_id, findings)

        # Mark scan as completed
        await scan_store.update_scan(scan_id, {
            "status": ScanStatus.COMPLETED.value,
            "finished_at": datetime.now(timezone.utc),
        })

        logger.info(
            "veracode_sync_scan_complete", scan_id=scan_id,
            build_id=build_id, findings=len(findings) if findings is not None else 0,
        )

        newest_build_id = build_id
        processed += 1

    await update_sync_state(
        last_synced_at=now,
        last_seen_build_id=newest_build_id or last_seen_build_id,
    )

    logger.info("veracode_sync_done", processed=processed)
    return processed


async def poll_loop() -> None:
    """Run the sync loop forever (legacy mode, replaced by Cloud Scheduler)."""
    settings = get_settings()
    interval = settings.veracode_sync_interval_seconds
    logger.info("veracode_poller_start", interval_seconds=interval)

    while True:
        try:
            await run_sync_once()
        except Exception as exc:
            logger.error("veracode_poller_error", error=str(exc))

        await asyncio.sleep(interval)


def main() -> None:
    from shared.logging import setup_logging
    setup_logging(get_settings().api_log_level)
    asyncio.run(poll_loop())


if __name__ == "__main__":
    main()
