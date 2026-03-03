"""Scan orchestrator — drives the full Veracode scan pipeline natively.

Sequence:
    1. Download repo from Bitbucket (archive API)
    2. Maven build → produce JAR
    3. Create Veracode build version natively
    4. Upload JAR to Veracode
    5. Start prescan → poll natively
    6. Start final scan → poll natively
    7. Get detailed report, static findings, SCA findings
    8. Store results to Firestore
    9. Clean up temp files
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone

from shared.config import get_settings
from shared.firestore_client import get_firestore_client
from shared.firestore_models import ScanArtifactDoc
from shared.logging import get_logger
from shared.repositories.finding_store import FindingStore
from shared.repositories.scan_store import ScanStore
from shared.pubsub_client import publish_analyze_finding

from scan_runner.normalize import normalize_findings
from scan_runner.repo_fetcher import cleanup_repo, clone_repo
from scan_runner.maven_builder import build_maven_project
from scan_runner import veracode_api

logger = get_logger(__name__)


async def run_scan_pipeline(scan_id: str) -> None:
    """Execute the full Veracode scan pipeline for a manual/scheduled scan natively."""
    settings = get_settings()
    db = get_firestore_client()
    scan_store = ScanStore(db)
    finding_store = FindingStore(db)

    # Load scan
    scan = await scan_store.get_scan(scan_id)
    if not scan:
        raise RuntimeError(f"Scan {scan_id} not found")

    repo_name = scan.repo_id
    app_id = settings.veracode_app_id
    app_guid = settings.veracode_app_guid
    sandbox_id = settings.veracode_sandbox_id or None
    sandbox_guid = settings.veracode_sandbox_guid or None

    if not app_id:
        raise RuntimeError("VERACODE_APP_ID is not configured")
    if not app_guid:
        raise RuntimeError("VERACODE_APP_GUID is not configured")

    repo_path = None
    try:
        # ── Step 1: Download repo from Bitbucket ─────────────────────────
        logger.info("pipeline_step_1_download", repo=repo_name, branch=scan.branch)
        repo_path = clone_repo(repo_name, scan.branch)

        # ── Step 2: Maven build ──────────────────────────────────────────
        logger.info("pipeline_step_2_maven_build", path=str(repo_path))
        artifact_path = build_maven_project(repo_path)

        artifact = ScanArtifactDoc(
            id=scan_id,
            scan_id=scan_id,
            artifact_uri=str(artifact_path),
            build_tool="maven",
        )
        await scan_store.add_artifact(scan_id, artifact)

        # ── Step 3: Create Veracode build ────────────────────────────────
        version = f"scan_{scan_id[:8]}_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}"
        logger.info("pipeline_step_3_create_build", version=version)
        
        build_id = veracode_api.create_new_build(app_id, version, sandbox_id, settings.veracode_analysis_base)
        await scan_store.update_scan(scan_id, {"external_build_id": build_id})

        # ── Step 4: Upload JAR ───────────────────────────────────────────
        logger.info("pipeline_step_4_upload", build_id=build_id)
        veracode_api.upload_artifact(app_id, str(repo_path), sandbox_id, settings.veracode_analysis_base)

        # ── Step 5: Start prescan ────────────────────────────────────────
        logger.info("pipeline_step_5_prescan")
        veracode_api.begin_prescan(app_id, sandbox_id, settings.veracode_analysis_base)

        # ── Step 6: Poll prescan until complete ──────────────────────────
        logger.info("pipeline_step_6_poll_prescan")
        veracode_api.poll_prescan_until_complete(
            app_id, sandbox_id, build_id,
            poll_interval=settings.scan_poll_interval_seconds,
            timeout=1200,
            api_base=settings.veracode_analysis_base
        )
        logger.info("pipeline_prescan_complete")

        # ── Step 7: Start final scan ─────────────────────────────────────
        logger.info("pipeline_step_7_final_scan")
        veracode_api.begin_final_scan(app_id, sandbox_id, settings.veracode_analysis_base)

        # ── Step 8: Poll final scan until complete ───────────────────────
        logger.info("pipeline_step_8_poll_final_scan")
        veracode_api.poll_final_scan_until_complete(
            app_id, sandbox_id, build_id,
            poll_interval=settings.scan_poll_interval_seconds,
            timeout=7200,
            api_base=settings.veracode_analysis_base
        )
        logger.info("pipeline_final_scan_complete")

        # ── Step 9: Get detailed report ──────────────────────────────────
        logger.info("pipeline_step_9_detailed_report")
        report = veracode_api.get_detailed_report(build_id, settings.veracode_analysis_base)

        report_artifact = ScanArtifactDoc(
            id=f"{scan_id}_report",
            scan_id=scan_id,
            artifact_uri=f"veracode://detailedreport/{build_id}",
            build_tool="veracode",
        )
        await scan_store.add_artifact(scan_id, report_artifact)
        flaw_count = len(report.get("flaws", []))

        # ── Step 10: Get static findings ─────────────────────────────────
        logger.info("pipeline_step_10_static_findings")
        static_result = veracode_api.get_static_findings(app_guid, sandbox_guid)
        static_count = static_result.get("total", 0)
        docs_static = normalize_findings(scan_id, static_result)

        # ── Step 11: Get SCA findings ────────────────────────────────────
        logger.info("pipeline_step_11_sca_findings")
        sca_result = veracode_api.get_sca_findings(app_guid, sandbox_guid)
        sca_count = sca_result.get("total", 0)
        docs_sca = normalize_findings(scan_id, sca_result)

        # ── Step 11.5: Save all findings to Firestore and trigger AI Analysis ──
        all_docs = docs_static + docs_sca
        if all_docs:
            logger.info("pipeline_saving_findings", count=len(all_docs))
            # Firestore batches allow max 500 writes; chunking to 450 to be safe
            for idx in range(0, len(all_docs), 450):
                await finding_store.create_findings(all_docs[idx:idx+450])
                
            logger.info("pipeline_triggering_ai_analysis", count=len(all_docs))
            for doc in all_docs:
                publish_analyze_finding(doc.id)

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
        print("\n\033[92mPipeline completed successfully!\033[0m")
    except KeyboardInterrupt:
        print("\nPipeline stopped by user")
        sys.exit(130)
    except Exception as e:
        print(f"\n\033[91mPipeline failed:\033[0m {e}")
        sys.exit(1)
