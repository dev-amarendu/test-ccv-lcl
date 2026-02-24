"""Normalizer worker for Veracode raw reports.

This module provides functions to persist the original Veracode payloads
(detailed/static/sca) into a `veracode_raw_reports` collection (or GCS for
large SCA blobs) and to normalize findings into `scans` and `findings`
collections using existing normalization logic.

Design:
- Called by poller/orchestrator once Veracode results are fetched.
- Writes a small metadata doc to `veracode_raw_reports/{report_id}` and
  uploads SCA JSON to GCS if above configured size limit.
- Calls existing `normalize_findings()` to produce FindingDoc objects and
  batch-writes them via FindingStore.
- Marks the raw report document as processed with counts and timestamps.
"""
from __future__ import annotations

import asyncio
import json
import uuid
from datetime import datetime, timezone
from typing import Any

from google.cloud import storage
from google.cloud.firestore_v1 import AsyncClient

from shared.config import get_settings
from shared.firestore_client import get_firestore_client
from shared.logging import get_logger
from shared.repositories.finding_store import FindingStore
from shared.repositories.scan_store import ScanStore
from scan_runner.normalize import normalize_findings

logger = get_logger(__name__)


async def _upload_to_gcs(bucket_name: str, blob_name: str, payload: bytes) -> str:
    """Upload bytes to GCS in a thread to avoid blocking the event loop.
    Returns the gs:// URI to the uploaded object.
    """
    def _upload():
        client = storage.Client()
        bucket = client.bucket(bucket_name)
        blob = bucket.blob(blob_name)
        blob.upload_from_string(payload, content_type="application/json")
        return f"gs://{bucket_name}/{blob_name}"

    uri = await asyncio.to_thread(_upload)
    return uri


async def normalize_and_store(scan_id: str, results: dict[str, Any]) -> None:
    """Persist raw results and normalized findings for a Veracode scan.

    Args:
        scan_id: the internal scan UUID assigned by CCV
        results: the dict returned by MCP/veracode client containing keys
                 like 'detailed', 'static', 'sca' or 'findings' depending on API.
    """
    settings = get_settings()
    db: AsyncClient = get_firestore_client()

    # Build raw report doc
    report_id = f"report-{scan_id}"
    now = datetime.now(timezone.utc)
    raw_doc: dict[str, Any] = {
        "id": report_id,
        "scan_id": scan_id,
        "build_id": results.get("build_id") or results.get("external_build_id"),
        "app_id": results.get("app_id"),
        "imported_at": now,
        "processed": {"normalized": False},
    }

    # Attach small detailed/static inline if present
    if "detailed" in results and results["detailed"]:
        raw_doc["raw_detailed"] = results["detailed"]
    if "static" in results and results["static"]:
        raw_doc["raw_static"] = results["static"]

    # Handle SCA payload: either inline (small) or upload to GCS and reference
    sca = results.get("sca") or results.get("sca_findings") or results.get("sca_response")
    if sca:
        sca_bytes = json.dumps(sca, default=str).encode("utf-8")
        if settings.gcs_raw_reports_bucket and len(sca_bytes) > settings.sca_inline_size_limit:
            # Upload to GCS
            blob_name = f"veracode/{report_id}/sca.json"
            try:
                gs_uri = await _upload_to_gcs(settings.gcs_raw_reports_bucket, blob_name, sca_bytes)
                raw_doc["sca_gcs_uri"] = gs_uri
            except Exception:
                logger.exception("sca_gcs_upload_failed", report_id=report_id)
                # fallback to inline if upload fails
                raw_doc["raw_sca"] = sca
        else:
            raw_doc["raw_sca"] = sca

    # Write raw report doc
    await db.collection("veracode_raw_reports").document(report_id).set({
        **raw_doc,
        # Firestore-friendly timestamp
        "imported_at": now,
    })
    logger.info("raw_report_saved", report_id=report_id, scan_id=scan_id)

    # Normalize findings using existing normalization function
    try:
        findings = normalize_findings(scan_id, results)
        # If we uploaded SCA to GCS and we still have an in-memory list, attach gcs_ref index
        sca_list = results.get("sca") or results.get("sca_findings") or results.get("sca_response")
        sca_uri = raw_doc.get("sca_gcs_uri")
        if sca_uri and sca_list:
            # Attach index mapping for findings that originate from SCA list items
            for idx, sca_item in enumerate(sca_list):
                for f in findings:
                    # match by equality of raw_source_json to the SCA item (best-effort)
                    if f.raw_source_json == sca_item:
                        f.gcs_ref = {"uri": sca_uri, "index_in_blob": idx}
                        break

        # batch create via FindingStore
        finding_store = FindingStore(db)
        if findings:
            await finding_store.batch_create(findings)
            count = len(findings)
        else:
            count = 0
    except Exception:
        logger.exception("normalization_failed", scan_id=scan_id)
        # mark raw report as errored
        await db.collection("veracode_raw_reports").document(report_id).update({
            "processed": {"normalized": False, "error": "normalization_failed"},
        })
        return []

    # Mark processed and record counts
    await db.collection("veracode_raw_reports").document(report_id).update({
        "processed": {"normalized": True, "findings_count": count, "last_processed_at": datetime.now(timezone.utc)}
    })
    logger.info("normalization_complete", report_id=report_id, findings=count)
    # Return created findings for further processing (e.g., enqueue analysis)
    return findings

