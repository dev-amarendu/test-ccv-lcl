"""Scan orchestrator — drives the full Veracode scan pipeline via MCP tools.

All Veracode interactions go through the MCP server:
    orchestrator → MCPClient (HTTP) → MCP Server → Veracode API

Sequence:
    1. Download repo from Bitbucket (direct — not via MCP)
    2. Maven build (direct — not via MCP)
    3. veracode.create_build → get build_id
    4. veracode.upload_artifact → upload JAR
    5. veracode.start_prescan → begin prescan
    6. veracode.get_prescan_results → poll until complete
    7. veracode.start_final_scan → begin full scan
    8. veracode.get_final_scan_status → poll until complete
    9. veracode.get_detailed_report → get report with flaws
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone

from shared.config import get_settings
from shared.firestore_client import get_firestore_client
from shared.firestore_models import ScanArtifactDoc
from shared.logging import get_logger
from shared.repositories.scan_store import ScanStore

from scan_runner.repo_fetcher import cleanup_repo, clone_repo
from scan_runner.maven_builder import build_maven_project
from scan_runner.veracode_upload_api import MCPClient

logger = get_logger(__name__)


async def run_scan_pipeline(scan_id: str) -> None:
    """Execute the full Veracode scan pipeline for a manual/scheduled scan."""
    settings = get_settings()
    db = get_firestore_client()
    mcp = MCPClient()

    scan_store = ScanStore(db)

    # Load scan
    scan = await scan_store.get_scan(scan_id)
    if not scan:
        raise RuntimeError(f"Scan {scan_id} not found")

    repo_name = scan.repo_id
    app_id = settings.veracode_app_id
    sandbox_id = settings.veracode_sandbox_id or None

    if not app_id:
        raise RuntimeError("VERACODE_APP_ID is not configured")

    repo_path = None
    try:
        # ── Step 1: Download repo from Bitbucket ─────────────────────────
        logger.info("pipeline_step_1_download", repo=repo_name, branch=scan.branch)
        repo_path = clone_repo(repo_name, scan.branch)

        # ── Step 2: Maven build ──────────────────────────────────────────
        logger.info("pipeline_step_2_maven_build", path=str(repo_path))
        artifact_path = build_maven_project(repo_path)

        # Store artifact reference in Firestore
        artifact = ScanArtifactDoc(
            id=scan_id,
            scan_id=scan_id,
            artifact_uri=str(artifact_path),
            build_tool="maven",
        )
        await scan_store.add_artifact(scan_id, artifact)

        # ── Step 3: Create Veracode build (via MCP) ──────────────────────
        version = f"scan_{scan_id[:8]}_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}"
        logger.info("pipeline_step_3_create_build", version=version)

        create_params = {"app_id": app_id, "version": version}
        if sandbox_id:
            create_params["sandbox_id"] = sandbox_id

        create_result = await mcp.call_tool("veracode.create_build", create_params)
        build_id = create_result.get("build_id", "")

        # Save build_id immediately
        await scan_store.update_scan(scan_id, {"external_build_id": build_id})

        # ── Step 4: Upload JAR (via MCP) ─────────────────────────────────
        logger.info("pipeline_step_4_upload", build_id=build_id)

        upload_params = {"app_id": app_id, "file_path": str(artifact_path)}
        if sandbox_id:
            upload_params["sandbox_id"] = sandbox_id

        await mcp.call_tool("veracode.upload_artifact", upload_params)

        # ── Step 5: Start prescan (via MCP) ──────────────────────────────
        logger.info("pipeline_step_5_prescan")

        prescan_params = {"app_id": app_id}
        if sandbox_id:
            prescan_params["sandbox_id"] = sandbox_id

        await mcp.call_tool("veracode.start_prescan", prescan_params)

        # ── Step 6: Poll prescan until complete ──────────────────────────
        logger.info("pipeline_step_6_poll_prescan")

        prescan_poll_params = {"app_id": app_id}
        if build_id:
            prescan_poll_params["build_id"] = build_id
        if sandbox_id:
            prescan_poll_params["sandbox_id"] = sandbox_id

        for attempt in range(settings.scan_poll_max_attempts):
            prescan_result = await mcp.call_tool(
                "veracode.get_prescan_results", prescan_poll_params
            )
            modules = prescan_result.get("modules", [])
            in_progress = any(
                m.get("status", "").strip() in ("Queued", "Pre-Scan Submitted", "Pre-Scan Running")
                for m in modules
            )

            if modules and not in_progress:
                logger.info("pipeline_prescan_complete", modules=len(modules))
                break

            logger.info("pipeline_prescan_waiting", attempt=attempt)
            await asyncio.sleep(settings.scan_poll_interval_seconds)
        else:
            raise RuntimeError("Prescan timed out waiting for completion")

        # ── Step 7: Start final scan (via MCP) ───────────────────────────
        logger.info("pipeline_step_7_final_scan")

        scan_params = {"app_id": app_id, "scan_all_top_level_modules": True}
        if sandbox_id:
            scan_params["sandbox_id"] = sandbox_id

        await mcp.call_tool("veracode.start_final_scan", scan_params)

        # ── Step 8: Poll final scan until complete ───────────────────────
        logger.info("pipeline_step_8_poll_final_scan")

        status_params = {"app_id": app_id}
        if build_id:
            status_params["build_id"] = build_id
        if sandbox_id:
            status_params["sandbox_id"] = sandbox_id

        for attempt in range(settings.scan_poll_max_attempts):
            status_result = await mcp.call_tool(
                "veracode.get_final_scan_status", status_params
            )
            if status_result.get("complete"):
                logger.info("pipeline_final_scan_complete")
                break

            logger.info(
                "pipeline_final_scan_waiting",
                attempt=attempt,
                status=status_result.get("status"),
            )
            await asyncio.sleep(settings.scan_poll_interval_seconds)
        else:
            raise RuntimeError("Final scan timed out waiting for completion")

        # ── Step 9: Get detailed report (via MCP) ────────────────────────
        logger.info("pipeline_step_9_detailed_report")

        report = await mcp.call_tool(
            "veracode.get_detailed_report", {"build_id": build_id}
        )

        # Store report reference
        report_artifact = ScanArtifactDoc(
            id=f"{scan_id}_report",
            scan_id=scan_id,
            artifact_uri=f"veracode://detailedreport/{build_id}",
            build_tool="veracode",
        )
        await scan_store.add_artifact(scan_id, report_artifact)

        flaw_count = len(report.get("flaws", []))

        # ── Step 10: Get static findings (via MCP) ───────────────────────
        logger.info("pipeline_step_10_static_findings")

        static_params = {"app_id": app_id}
        if sandbox_id:
            static_params["sandbox_id"] = sandbox_id

        static_result = await mcp.call_tool(
            "veracode.get_static_findings", static_params
        )
        static_count = static_result.get("total", 0)
        logger.info("pipeline_static_findings_done", count=static_count)

        # ── Step 11: Get SCA findings (via MCP) ──────────────────────────
        logger.info("pipeline_step_11_sca_findings")

        sca_params = {"app_id": app_id}
        if sandbox_id:
            sca_params["sandbox_id"] = sandbox_id

        sca_result = await mcp.call_tool(
            "veracode.get_sca_findings", sca_params
        )
        sca_count = sca_result.get("total", 0)
        logger.info("pipeline_sca_findings_done", count=sca_count)

        # ── Step 12: Update scan record ──────────────────────────────────
        await scan_store.update_scan(scan_id, {
            "external_build_id": build_id,
            "external_app_id": app_id,
        })

        logger.info(
            "pipeline_complete",
            scan_id=scan_id,
            build_id=build_id,
            flaws=flaw_count,
            static_findings=static_count,
            sca_findings=sca_count,
        )

    finally:
        # ── Cleanup temp files ───────────────────────────────────────────
        if repo_path:
            cleanup_repo(repo_path)


if __name__ == "__main__":
    import argparse
    import sys

    # Setup basic logging for local test runs
    from shared.logging import setup_logging
    setup_logging("DEBUG")

    parser = argparse.ArgumentParser(description="Run the orchestrator pipeline manually")
    parser.add_argument("--scan-id", required=True, help="Scan ID to process from Firestore")
    
    args = parser.parse_args()

    try:
        asyncio.run(run_scan_pipeline(args.scan_id))
        print("\n\033[92mPipeling completed successfully!\033[0m")
    except KeyboardInterrupt:
        print("\nPipeline stopped by user")
        sys.exit(130)
    except Exception as e:
        print(f"\n\033[91mPipeline failed:\033[0m {e}")
        sys.exit(1)
