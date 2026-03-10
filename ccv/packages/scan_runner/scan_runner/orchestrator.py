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
from shared.repo_fetcher import cleanup_repo, clone_repo
from scan_runner.maven_builder import build_maven_project
from scan_runner import veracode_api

logger = get_logger(__name__)

SNIPPET_CONTEXT_LINES = 10  # Lines above/below the target line to include


def _extract_snippets(repo_path: str, all_docs: list) -> None:
    """Walk through findings and attach code_snippet_json from the local repo.

    For each finding that has a valid file_path (not 'unknown') and line number,
    we try to read the source file from the downloaded repo and extract a
    window of ±SNIPPET_CONTEXT_LINES around the target line.

    Mutates the FindingDoc objects in-place.
    """
    import os
    from pathlib import Path

    repo = Path(repo_path)
    # Pre-build a filename→path index for fuzzy matching
    file_index: dict[str, Path] = {}
    for root, _, files in os.walk(repo):
        if any(skip in root for skip in (".git", "node_modules", "target", "__pycache__")):
            continue
        for fname in files:
            full = Path(root) / fname
            file_index[fname.lower()] = full

    for doc in all_docs:
        try:
            if doc.code_snippet_json and doc.code_snippet_json.get("snippet"):
                continue  # Already has a snippet

            fp = doc.file_path
            if not fp or fp.lower() == "unknown":
                continue

            # Try exact path match relative to repo root
            candidate = repo / fp
            if not candidate.is_file():
                # Try just the filename (Veracode often returns just the basename)
                basename = os.path.basename(fp).lower()
                candidate = file_index.get(basename)
                if not candidate or not candidate.is_file():
                    continue

            # Read and extract context window
            try:
                content = candidate.read_text(encoding="utf-8", errors="ignore")
            except Exception:
                continue

            lines = content.splitlines()
            target_line = doc.line or 1
            start = max(0, target_line - SNIPPET_CONTEXT_LINES - 1)
            end = min(len(lines), target_line + SNIPPET_CONTEXT_LINES)
            snippet_lines = lines[start:end]

            if snippet_lines:
                rel_path = str(candidate.relative_to(repo)) if repo in candidate.parents or candidate.parent == repo else fp
                doc.code_snippet_json = {
                    "snippet": "\n".join(snippet_lines),
                    "file_path": rel_path,
                    "start_line": start + 1,
                    "highlight_lines": [target_line] if doc.line else [],
                }
        except Exception:
            # Never let snippet extraction crash the pipeline
            continue


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
        docs_sca = []
        sca_count = 0
        try:
            sca_result = veracode_api.get_sca_findings(app_guid, sandbox_guid)
            sca_count = sca_result.get("total", 0)
            logger.info("sca_result_structure", total=sca_count, 
                       keys=list(sca_result.keys()) if isinstance(sca_result, dict) else str(type(sca_result)))
            docs_sca = normalize_findings(scan_id, sca_result)
        except Exception as sca_exc:
            import traceback
            logger.error("sca_findings_failed", error=str(sca_exc), traceback=traceback.format_exc())

        # ── Step 11.5: Save all findings to Firestore and trigger AI Analysis ──
        docs_report = []
        try:
            docs_report = normalize_findings(scan_id, report)
        except Exception as rpt_exc:
            import traceback
            logger.error("report_normalization_failed", error=str(rpt_exc), traceback=traceback.format_exc())
        
        # Deduplicate across the 3 streams (static REST, SCA REST, Detailed XML)
        all_docs = []
        seen = set()
        for doc in docs_static + docs_sca + docs_report:
            if doc.fingerprint not in seen:
                all_docs.append(doc)
                seen.add(doc.fingerprint)
                
        if all_docs:
            # ── Step 11.6: Extract code snippets while repo is still on disk ──
            if repo_path:
                logger.info("pipeline_extracting_snippets", count=len(all_docs))
                _extract_snippets(repo_path, all_docs)
                snippets_found = sum(1 for d in all_docs if d.code_snippet_json and d.code_snippet_json.get("snippet"))
                logger.info("pipeline_snippets_extracted", found=snippets_found, total=len(all_docs))

            logger.info("pipeline_saving_findings", count=len(all_docs))

            # ── Dedup check: remove findings already in Firestore for this scan ──
            existing_fps = set()
            try:
                from google.cloud.firestore_v1 import FieldFilter
                existing_query = db.collection("findings").where(
                    filter=FieldFilter("scan_id", "==", scan_id)
                ).select(["fingerprint"])
                async for snap in existing_query.stream():
                    fp = snap.to_dict().get("fingerprint")
                    if fp:
                        existing_fps.add(fp)
            except Exception as dedup_exc:
                logger.warning("dedup_query_failed", error=str(dedup_exc))

            if existing_fps:
                before = len(all_docs)
                all_docs = [d for d in all_docs if d.fingerprint not in existing_fps]
                skipped = before - len(all_docs)
                if skipped:
                    logger.info("pipeline_dedup_skipped", skipped=skipped, remaining=len(all_docs))

            # Firestore batches allow max 500 writes; chunking to 450 to be safe
            for idx in range(0, len(all_docs), 450):
                await finding_store.create_findings(all_docs[idx:idx+450])
                
            logger.info("pipeline_triggering_ai_analysis", scan_id=scan_id)
            try:
                from analysis_agent.agent import analyze_scan
                await analyze_scan(scan_id)
            except ImportError:
                logger.warning("analysis_agent_not_available_for_scan_analysis")
                # Fallback: publish per-finding messages
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
