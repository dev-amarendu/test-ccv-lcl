"""ADK Function Tools for the CCV Analysis Agent.

Each function is passed to the ADK Agent's ``tools=[...]`` list.
ADK auto-wraps plain Python functions as FunctionTools.

Tools use **synchronous** I/O because ADK executes tool functions
within its own async event-loop; sync functions avoid nested-loop issues.
"""

from __future__ import annotations

import httpx

from google.cloud import firestore

from shared.config import get_settings
from shared.logging import get_logger

logger = get_logger(__name__)

KB_SERVICE_URL = "http://localhost:8002"


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

import os
import glob
from pathlib import Path
from shared.repositories.scan_store import ScanStore

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
    scan_store = ScanStore(db)
    
    import asyncio
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
    scan = loop.run_until_complete(scan_store.get_scan(scan_id))
    if not scan:
        return {"status": "error", "message": f"Scan {scan_id} not found."}

    from shared.repo_fetcher import clone_repo, cleanup_repo
    repo_path = None
    try:
        repo_path = clone_repo(scan.repo_id, scan.branch)
        
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
                    
                snippet = "\n".join(content.splitlines()[:150]) # Return up to 150 lines to keep context manageable
                matches.append({
                    "file_path": str(rel_path),
                    "snippet": snippet
                })
                
                # Break early to avoid massive LLM context explosion if too many matches
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
