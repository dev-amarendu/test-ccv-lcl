"""Scan orchestrator — drives the full scan pipeline via MCP tools.

Sequence:
    upload_artifact -> start_prescan -> get_prescan_results ->
    start_final_scan -> poll status -> get_final_results ->
    normalize -> store findings -> enqueue analysis
"""

from __future__ import annotations

import asyncio

from shared.config import get_settings
from shared.firestore_client import get_firestore_client
from shared.firestore_models import ScanArtifactDoc
from shared.logging import get_logger
from shared.repositories.repos import RepoStore
from shared.repositories.scan_store import ScanStore
from shared.repositories.finding_store import FindingStore

from scan_runner.repo_fetcher import cleanup_repo, clone_repo
from scan_runner.maven_builder import build_maven_project
from scan_runner.veracode_upload_api import MCPClient
from scan_runner.normalize import normalize_findings
from scan_runner.enqueue_analysis import enqueue_analysis_jobs

logger = get_logger(__name__)


async def run_scan_pipeline(scan_id: str) -> None:
    """Execute the full Veracode scan pipeline for a manual/scheduled scan."""
    settings = get_settings()
    db = get_firestore_client()
    mcp = MCPClient()

    scan_store = ScanStore(db)
    repo_store = RepoStore(db)
    finding_store = FindingStore(db)

    # Load scan + repo
    scan = await scan_store.get_scan(scan_id)
    if not scan:
        raise RuntimeError(f"Scan {scan_id} not found")

    repo = await repo_store.get_repo(scan.repo_id)
    if not repo:
        raise RuntimeError(f"Repo {scan.repo_id} not found")

    app_id = settings.veracode_app_id
    if not app_id:
        raise RuntimeError("VERACODE_APP_ID is not configured")

    repo_path = None
    try:
        # 1. Clone repo
        logger.info("pipeline_clone", repo=repo.name, branch=scan.branch)
        repo_path = clone_repo(repo.name, scan.branch)

        # 2. Maven build
        logger.info("pipeline_maven_build")
        artifact_path = build_maven_project(repo_path)

        # 3. Store artifact reference
        artifact = ScanArtifactDoc(
            id=scan_id,  # use scan_id as artifact doc id
            scan_id=scan_id,
            artifact_uri=str(artifact_path),
            build_tool="maven",
        )
        await scan_store.add_artifact(scan_id, artifact)

        # 4. Upload artifact via MCP
        logger.info("pipeline_upload")
        await mcp.call_tool("veracode.upload_artifact", {
            "app_id": app_id,
            "file_path": str(artifact_path),
        })

        # 5. Start prescan
        logger.info("pipeline_prescan")
        prescan_result = await mcp.call_tool("veracode.start_prescan", {
            "app_id": app_id,
        })
        build_id = prescan_result.get("build_id", "")

        # 6. Get prescan results (wait briefly)
        await asyncio.sleep(5)
        logger.info("pipeline_get_prescan_results")
        await mcp.call_tool("veracode.get_prescan_results", {
            "app_id": app_id,
            "build_id": build_id,
        })

        # 7. Start final scan
        logger.info("pipeline_start_scan")
        await mcp.call_tool("veracode.start_final_scan", {
            "app_id": app_id,
        })

        # 8. Poll scan status
        logger.info("pipeline_poll_status")
        for attempt in range(settings.scan_poll_max_attempts):
            status_result = await mcp.call_tool("veracode.get_final_scan_status", {
                "app_id": app_id,
            })
            if status_result.get("complete"):
                break
            logger.info("pipeline_poll_waiting", attempt=attempt, status=status_result.get("status"))
            await asyncio.sleep(settings.scan_poll_interval_seconds)
        else:
            raise RuntimeError("Scan timed out waiting for completion")

        # 9. Get final results
        logger.info("pipeline_get_results")
        results = await mcp.call_tool("veracode.get_final_results", {
            "app_id": app_id,
        })

        # 10. Persist raw results and normalize + store findings via normalizer.
        # This will save the vendor payload to veracode_raw_reports (or GCS)
        # and create normalized FindingDoc documents.
        logger.info("pipeline_normalize")
        from scan_runner.normalizer import normalize_and_store

        findings = await normalize_and_store(scan_id, results)

        # 11. Enqueue analysis jobs via Pub/Sub
        logger.info("pipeline_enqueue_analysis", count=len(findings) if findings is not None else 0)
        await enqueue_analysis_jobs(scan_id, findings)

        # 12. Update external_build_id
        await scan_store.update_scan(scan_id, {"external_build_id": build_id})

        logger.info("pipeline_complete", scan_id=scan_id, findings=len(findings))

    finally:
        if repo_path:
            cleanup_repo(repo_path)
