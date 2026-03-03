"""Tool registry — maps tool names to async handler functions."""

from __future__ import annotations

from typing import Any, Callable, Coroutine

from mcp_server.tools.veracode_tools import veracode_run_full_scan
from mcp_server.tools.bitbucket_tools import bitbucket_get_pull_request
from mcp_server.tools.analysis_tools import mcp_request_analysis, mcp_get_finding_analysis
from mcp_server.tools.kb_tools import mcp_kb_search, mcp_kb_get_card

ToolHandler = Callable[[dict[str, Any]], Coroutine[Any, Any, Any]]

_registry: dict[str, ToolHandler] | None = None


def get_tool_registry() -> dict[str, ToolHandler]:
    """Return the singleton tool registry."""
    global _registry
    if _registry is None:
        _registry = {
            # Veracode primary orchestrator tool
            "veracode.run_full_scan": veracode_run_full_scan,
            
            # Bitbucket (optional)
            "bitbucket.get_pull_request": bitbucket_get_pull_request,

            # Analyst Agent Tools
            "analysis.request_analysis": mcp_request_analysis,
            "analysis.get_analysis": mcp_get_finding_analysis,

            # Knowledge Base Tools
            "kb.search": mcp_kb_search,
            "kb.get_card": mcp_kb_get_card,
        }
    return _registry
