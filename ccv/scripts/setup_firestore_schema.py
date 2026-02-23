#!/usr/bin/env python3
"""
Setup Firestore schema helpers for CCV.

This script creates lightweight marker documents and example documents
for the collections the application expects. It is intentionally
idempotent and safe to run multiple times.

Usage:
  python ccv/scripts/setup_firestore_schema.py

Requirements:
  - Application Default Credentials (ADC) set or GOOGLE_APPLICATION_CREDENTIALS
  - FIRESTORE_PROJECT_ID and FIRESTORE_DATABASE set via env or shared.config

What it does:
  - Connects to Firestore using shared.get_settings()
  - Creates marker/example documents for:
      veracode_raw_reports, scans, scans/{scan_id}/artifacts,
      findings, finding_analyses, kb_fix_cards, schedules, audit_logs, sync_state
  - Prints instructions for creating composite indexes (also writes firestore.indexes.json)

Notes:
  - This does NOT create Firestore composite indexes programmatically.
    Use the generated `firestore.indexes.json` with `gcloud firestore indexes composite create`
    or upload via the Firebase/Firestore console.
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone

from google.cloud import firestore

from shared.config import get_settings


def get_client():
    settings = get_settings()
    # If firestore_project_id is empty, the client will fall back to ADC project
    kwargs = {}
    if settings.firestore_project_id:
        kwargs["project"] = settings.firestore_project_id
    # firestore-python client ignores 'database' for standard uses; kept for completeness
    client = firestore.Client(**kwargs)
    return client


def create_marker_docs(client: firestore.Client) -> None:
    """Create one small document per collection to ensure collection visibility and example shape.
    The function is idempotent: it will set documents with fixed IDs.
    """
    now = datetime.now(timezone.utc).isoformat()

    # veracode_raw_reports: small metadata doc pointing to where raw SCA should live (GCS)
    raw_reports_ref = client.collection("veracode_raw_reports").document("__schema_marker__")
    raw_reports_ref.set({
        "example": True,
        "build_id": "63347966",
        "app_id": "164494",
        "imported_at": now,
        "processed": {"normalized": False},
        "note": "This is a schema marker. Large raw SCA payloads should be stored in GCS and referenced by sca_gcs_uri."
    }, merge=True)

    # scans: example ScanDoc
    scans_ref = client.collection("scans").document("__schema_marker__")
    scans_ref.set({
        "id": "__schema_marker__",
        "repo_id": "repo-mark",
        "branch": "main",
        "trigger_type": "MANUAL",
        "status": "QUEUED",
        "external_build_id": "63347966",
        "created_at": now,
    }, merge=True)

    # create an artifacts subcollection under the scan marker (demonstrates subcollection)
    art_ref = client.collection("scans").document("__schema_marker__").collection("artifacts").document("__schema_marker__")
    art_ref.set({
        "id": "__schema_marker__",
        "scan_id": "__schema_marker__",
        "artifact_uri": "gs://example-bucket/path/to/artifact.zip",
        "created_at": now,
    }, merge=True)

    # findings: example FindingDoc
    findings_ref = client.collection("findings").document("__schema_marker__")
    findings_ref.set({
        "id": "__schema_marker__",
        "scan_id": "__schema_marker__",
        "cwe_id": 79,
        "severity": "High",
        "title": "Example finding marker",
        "file_path": "src/example.py",
        "fingerprint": "example-fingerprint",
        "created_at": now,
    }, merge=True)

    # finding_analyses
    analyses_ref = client.collection("finding_analyses").document("__schema_marker__")
    analyses_ref.set({
        "id": "__schema_marker__",
        "finding_id": "__schema_marker__",
        "model_name": "gemini-2.0-flash",
        "root_cause": "Example",
        "fix_guidance": "Example",
        "created_at": now,
    }, merge=True)

    # kb_fix_cards
    kb_ref = client.collection("kb_fix_cards").document("__schema_marker__")
    kb_ref.set({
        "id": "__schema_marker__",
        "cwe_id": 79,
        "title": "Example KB card",
        "content": "Use parameterized queries",
        "approved": True,
        "created_at": now,
    }, merge=True)

    # schedules
    sched_ref = client.collection("schedules").document("__schema_marker__")
    sched_ref.set({
        "id": "__schema_marker__",
        "repo_id": "repo-mark",
        "branch": "main",
        "interval_minutes": 60,
        "enabled": True,
        "next_run_at": now,
        "created_at": now,
    }, merge=True)

    # audit_logs
    audit_ref = client.collection("audit_logs").document("__schema_marker__")
    audit_ref.set({
        "id": "__schema_marker__",
        "request_id": "req-000",
        "actor": "system",
        "action": "schema_init",
        "entity_type": "schema",
        "status": "created",
        "created_at": now,
    }, merge=True)

    # sync_state singleton
    sync_ref = client.collection("sync_state").document("veracode")
    sync_ref.set({
        "last_synced_at": None,
        "last_seen_build_id": None,
    }, merge=True)

    print("Created marker/example documents for collections (id: __schema_marker__).")


def write_indexes_file(path: str = "ccv/firestore.indexes.json") -> None:
    """Write a recommended firestore.indexes.json file for composite indexes used in CCV."""
    indexes = {
        "indexes": [
            {
                "collectionGroup": "findings",
                "queryScope": "COLLECTION",
                "fields": [
                    {"fieldPath": "scan_id", "order": "ASCENDING"},
                    {"fieldPath": "severity", "order": "DESCENDING"}
                ]
            },
            {
                "collectionGroup": "scans",
                "queryScope": "COLLECTION",
                "fields": [
                    {"fieldPath": "repo_id", "order": "ASCENDING"},
                    {"fieldPath": "created_at", "order": "DESCENDING"}
                ]
            }
        ],
        "fieldOverrides": []
    }
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(indexes, fh, indent=2)
    print(f"Wrote recommended composite indexes to {path}. Upload these via gcloud or the console.")


def main() -> None:
    print("Setting up Firestore schema markers for CCV...")
    client = get_client()
    create_marker_docs(client)
    write_indexes_file()
    print("Done. Next steps:")
    print(" - Review ccv/firestore.indexes.json and create composite indexes in Firestore.")
    print(" - Ensure service account used by services has proper IAM (datastore.user, storage.objectViewer/uploader as needed).")


if __name__ == "__main__":
    main()

