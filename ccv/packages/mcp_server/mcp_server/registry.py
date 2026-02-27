"""Tool registry — maps tool names to async handler functions."""

from __future__ import annotations

from typing import Any, Callable, Coroutine

from mcp_server.tools.veracode_tools import (
    veracode_create_build,
    veracode_get_detailed_report,
    veracode_get_final_results,
    veracode_get_final_scan_status,
    veracode_get_prescan_results,
    veracode_get_sca_findings,
    veracode_get_scan_metadata,
    veracode_get_static_findings,
    veracode_list_recent_scans,
    veracode_start_final_scan,
    veracode_start_prescan,
    veracode_upload_artifact,
)
from mcp_server.tools.bitbucket_tools import bitbucket_get_pull_request

ToolHandler = Callable[[dict[str, Any]], Coroutine[Any, Any, Any]]

_registry: dict[str, ToolHandler] | None = None


def get_tool_registry() -> dict[str, ToolHandler]:
    """Return the singleton tool registry."""
    global _registry
    if _registry is None:
        _registry = {
            # Veracode primary tools
            "veracode.create_build": veracode_create_build,
            "veracode.upload_artifact": veracode_upload_artifact,
            "veracode.start_prescan": veracode_start_prescan,
            "veracode.get_prescan_results": veracode_get_prescan_results,
            "veracode.start_final_scan": veracode_start_final_scan,
            "veracode.get_final_scan_status": veracode_get_final_scan_status,
            "veracode.get_final_results": veracode_get_final_results,
            "veracode.get_detailed_report": veracode_get_detailed_report,
            "veracode.get_static_findings": veracode_get_static_findings,
            "veracode.get_sca_findings": veracode_get_sca_findings,
            # Veracode sync/polling tools
            "veracode.list_recent_scans": veracode_list_recent_scans,
            "veracode.get_scan_metadata": veracode_get_scan_metadata,
            # Aliases
            "veracode.start_scan": veracode_start_final_scan,
            "veracode.get_scan_status": veracode_get_final_scan_status,
            "veracode.get_findings": veracode_get_final_results,
            # Bitbucket (optional)
            "bitbucket.get_pull_request": bitbucket_get_pull_request,
        }
    return _registry
