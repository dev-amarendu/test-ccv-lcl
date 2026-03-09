"""ADK Function Tools for the CCV Analysis Agent.

Each function is passed to the ADK Agent's ``tools=[...]`` list.
ADK auto-wraps plain Python functions as FunctionTools.

Tools use **synchronous** I/O because ADK executes tool functions
within its own async event-loop; sync functions avoid nested-loop issues.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import httpx
from google.cloud import firestore

from shared.config import get_settings
from shared.logging import get_logger

logger = get_logger(__name__)

KB_SERVICE_URL = "http://localhost:8002"


# ── Tool 1: lookup_kb_fix_card ───────────────────────────────────────────────


def lookup_kb_fix_card(cwe_id: int) -> dict:
    """Look up a Knowledge Base Fix Card for a given CWE identifier.

    Searches the CCV knowledge base for remediation guidance matching
    a Common Weakness Enumeration (CWE) ID.

    Args:
        cwe_id: The numeric CWE identifier (e.g. 79 for XSS,
                89 for SQL Injection, 502 for Deserialization).

    Returns:
        dict with keys:
            status: 'found' if a fix card exists, 'not_found' otherwise.
            cwe_id: The CWE identifier queried.
            content: The fix card remediation text (only when status='found').
            source: Where the card came from ('kb_service' or 'firestore').
    """
    # ── Try KB micro-service API first ────────────────────────────────────
    try:
        with httpx.Client(timeout=5) as client:
            resp = client.get(f"{KB_SERVICE_URL}/kb/v1/cards/{cwe_id}")
        if resp.status_code == 200:
            data = resp.json()
            return {
                "status": "found",
                "cwe_id": cwe_id,
                "content": data.get("content", ""),
                "source": "kb_service",
            }
    except Exception:
        logger.debug("kb_service_unavailable_for_tool", cwe_id=cwe_id)

    # ── Fallback: direct Firestore query (sync client) ────────────────────
    try:
        settings = get_settings()
        db = firestore.Client(
            project=settings.firestore_project_id,
            database=settings.firestore_database,
        )
        docs = db.collection("kb_fix_cards").where("cwe_id", "==", cwe_id).limit(1).get()
        for doc in docs:
            data = doc.to_dict()
            return {
                "status": "found",
                "cwe_id": cwe_id,
                "content": data.get("content", ""),
                "source": "firestore",
            }
    except Exception:
        logger.warning("kb_firestore_fallback_failed_in_tool", cwe_id=cwe_id, exc_info=True)

    return {
        "status": "not_found",
        "cwe_id": cwe_id,
        "message": f"No fix card found for CWE-{cwe_id}",
    }


# ── Tool 2: get_documents_by_scan_id ─────────────────────────────────────────


def get_documents_by_scan_id(scan_id: str) -> dict:
    """Retrieve all available report documents for a given scan ID.

    Fetches findings from the ``findings`` collection filtered by scan_id,
    and returns them grouped by report type (detailed_report, sca_report,
    static_report) based on the raw_source_json content.

    Also retrieves the scan metadata for context (repo, branch, status).

    Args:
        scan_id: The scan ID to look up findings for.

    Returns:
        dict with keys:
            scan_id: The scan ID queried.
            scan_meta: dict with repo_id, branch, status, trigger_type.
            detailed_report: list of findings from the XML detailed report.
            sca_report: list of SCA findings.
            static_report: list of static analysis findings.
            total_findings: Total number of findings across all reports.
    """
    settings = get_settings()
    db = firestore.Client(
        project=settings.firestore_project_id,
        database=settings.firestore_database,
    )

    result = {
        "scan_id": scan_id,
        "scan_meta": {},
        "detailed_report": [],
        "sca_report": [],
        "static_report": [],
        "total_findings": 0,
    }

    # ── Fetch scan metadata ──────────────────────────────────────────────
    try:
        scan_snap = db.collection("scans").document(scan_id).get()
        if scan_snap.exists:
            scan_data = scan_snap.to_dict()
            result["scan_meta"] = {
                "repo_id": scan_data.get("repo_id", ""),
                "branch": scan_data.get("branch", ""),
                "status": scan_data.get("status", ""),
                "trigger_type": scan_data.get("trigger_type", ""),
                "external_build_id": scan_data.get("external_build_id", ""),
            }
    except Exception:
        logger.warning("get_documents_scan_meta_failed", scan_id=scan_id, exc_info=True)

    # ── Fetch all findings for this scan ──────────────────────────────────
    try:
        findings_query = db.collection("findings").where("scan_id", "==", scan_id).limit(500).get()

        for doc in findings_query:
            finding = doc.to_dict()
            # Build a compact finding summary for the LLM
            summary = {
                "id": finding.get("id", doc.id),
                "cwe_id": finding.get("cwe_id"),
                "severity": finding.get("severity", ""),
                "title": finding.get("title", ""),
                "file_path": finding.get("file_path", "unknown"),
                "line": finding.get("line"),
            }

            # Include code snippet if available
            snippet_json = finding.get("code_snippet_json")
            if snippet_json and isinstance(snippet_json, dict):
                snippet = snippet_json.get("snippet", "")
                if snippet:
                    # Truncate to keep LLM context manageable
                    summary["code_snippet"] = snippet[:2000]

            # Classify by scan type from raw_source_json
            raw = finding.get("raw_source_json", {}) or {}
            scan_type = raw.get("scan_type", "").upper()

            if scan_type == "SCA":
                result["sca_report"].append(summary)
            elif scan_type == "STATIC":
                result["static_report"].append(summary)
            else:
                # Findings from the XML detailed report have fields like
                # 'issueid', 'categoryname', 'sourcefile', etc.
                if raw.get("issueid") or raw.get("categoryname"):
                    # Include extra context from the detailed report
                    summary["description"] = raw.get("description", "")
                    summary["categoryname"] = raw.get("categoryname", "")
                    result["detailed_report"].append(summary)
                else:
                    # Default to static
                    result["static_report"].append(summary)

        result["total_findings"] = (
            len(result["detailed_report"])
            + len(result["sca_report"])
            + len(result["static_report"])
        )

    except Exception:
        logger.error("get_documents_findings_failed", scan_id=scan_id, exc_info=True)

    logger.info(
        "get_documents_by_scan_id_done",
        scan_id=scan_id,
        detailed=len(result["detailed_report"]),
        sca=len(result["sca_report"]),
        static=len(result["static_report"]),
    )
    return result


# ── Tool 3: save_combined_analysis ───────────────────────────────────────────


def save_combined_analysis(scan_id: str, analysis: str) -> dict:
    """Save the combined analysis output for a scan to Firestore.

    Persists the LLM-generated analysis JSON as a document in the
    ``scan_analyses`` collection, keyed by scan_id.

    Args:
        scan_id: The scan ID this analysis belongs to.
        analysis: The full analysis JSON output as a string.

    Returns:
        dict with status and the document ID.
    """
    settings = get_settings()
    db = firestore.Client(
        project=settings.firestore_project_id,
        database=settings.firestore_database,
    )

    try:
        parsed = json.loads(analysis)
    except json.JSONDecodeError:
        parsed = {"raw_text": analysis}

    from datetime import datetime, timezone
    from shared.utils import generate_uuid

    doc_id = str(generate_uuid())
    doc_data = {
        "id": doc_id,
        "scan_id": scan_id,
        "analysis": parsed,
        "model_name": settings.llm_model if hasattr(settings, "llm_model") else "unknown",
        "created_at": datetime.now(timezone.utc),
    }

    try:
        db.collection("scan_analyses").document(doc_id).set(doc_data)
        logger.info("save_combined_analysis_done", scan_id=scan_id, doc_id=doc_id)
        return {"status": "saved", "id": doc_id, "scan_id": scan_id}
    except Exception as exc:
        logger.error("save_combined_analysis_failed", scan_id=scan_id, error=str(exc), exc_info=True)
        return {"status": "error", "message": str(exc)}


# ── Tool 4: search_codebase_for_snippet ──────────────────────────────────────


def search_codebase_for_snippet(scan_id: str, search_filename: str = "", search_keyword: str = "") -> dict:
    """Search the codebase for a file or a snippet of code.

    This tool should be used when the finding's file_path is 'unknown',
    or when you need the complete context of a file.

    It downloads the repository zip, searches, and extracts matching files.

    Args:
        scan_id: The ID of the scan that the finding belongs to.
        search_filename: Optional. The name of the file to search for (e.g. 'AuthContext.tsx').
        search_keyword: Optional. A keyword to search for within file contents (e.g. a class name or function).

    Returns:
        dict with keys:
            status: 'found' or 'not_found'
            matches: A list of dicts with 'file_path' and 'snippet' (first 150 lines).
    """
    settings = get_settings()
    db = firestore.Client(
        project=settings.firestore_project_id,
        database=settings.firestore_database,
    )

    # Get scan metadata synchronously
    scan_snap = db.collection("scans").document(scan_id).get()
    if not scan_snap.exists:
        return {"status": "error", "message": f"Scan {scan_id} not found."}

    scan_data = scan_snap.to_dict()
    repo_name = scan_data.get("repo_id", "")
    branch = scan_data.get("branch", "main")

    if not repo_name:
        return {"status": "error", "message": "Scan has no repo_id"}

    from shared.repo_fetcher import clone_repo, cleanup_repo
    repo_path = None
    try:
        repo_path = clone_repo(repo_name, branch)

        matches = []
        for root, _, files in os.walk(repo_path):
            for file in files:
                # Filter out obvious binaries and vendored dependencies
                if file.endswith(('.jar', '.class', '.pyc', '.png', '.jpg', '.zip', '.tar.gz')):
                    continue
                if "node_modules" in root or ".git" in root or "target" in root:
                    continue

                full_path = Path(root) / file
                rel_path = full_path.relative_to(repo_path)

                # Check filename match
                if search_filename and search_filename.lower() not in file.lower():
                    continue

                # Read content safely
                try:
                    content = full_path.read_text(encoding='utf-8', errors='ignore')
                except Exception:
                    continue

                # Check keyword match
                if search_keyword and search_keyword.lower() not in content.lower():
                    continue

                snippet = "\n".join(content.splitlines()[:150])  # Return up to 150 lines
                matches.append({
                    "file_path": str(rel_path),
                    "snippet": snippet
                })

                # Break early to avoid massive LLM context explosion
                if len(matches) >= 3:
                    break
            if len(matches) >= 3:
                break

        if not matches:
            return {"status": "not_found", "message": "No matching files or keywords found in the repository."}

        return {"status": "found", "matches": matches}

    except Exception as e:
        logger.error("search_codebase_failed", exc_info=True)
        return {"status": "error", "message": str(e)}
    finally:
        if repo_path:
            cleanup_repo(repo_path)
