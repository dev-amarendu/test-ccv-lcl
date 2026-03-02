"""Veracode MCP tools — Exposes a single tool that runs the full scan pipeline directly.

Instead of passing each API call over HTTP via MCP, the MCP Server directly triggers
the native scan runner pipeline, acting as a single, powerful agent tool.
"""

from __future__ import annotations

from typing import Any
from shared.logging import get_logger

logger = get_logger(__name__)


async def veracode_run_full_scan(params: dict[str, Any]) -> dict:
    """Run the complete Veracode scan pipeline (download, build, upload, scan, report).

    This triggers the native scan coordinator internally. It blocks until the scan
    is fully completed successfully or throws an error.

    Params:
        scan_id: str — The document ID of the scan record in Firestore.
    """
    scan_id = params.get("scan_id")
    if not scan_id:
        return {"error": "Missing required parameter: scan_id"}

    logger.info("mcp_veracode_run_full_scan_start", scan_id=scan_id)

    try:
        from scan_runner.orchestrator import run_scan_pipeline

        # Run the full pipeline natively. This may take hours for large apps.
        await run_scan_pipeline(scan_id)

        logger.info("mcp_veracode_run_full_scan_success", scan_id=scan_id)
        return {"status": "success", "scan_id": scan_id}

    except Exception as exc:
        logger.error("mcp_veracode_run_full_scan_error", scan_id=scan_id, error=str(exc))
        return {"error": str(exc), "scan_id": scan_id}
