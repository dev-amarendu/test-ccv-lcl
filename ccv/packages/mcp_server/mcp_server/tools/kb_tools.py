"""Knowledge Base (KB) tools for the MCP server."""

from __future__ import annotations

import logging
from typing import Any

from kb_service.store import get_fix_card, vector_search

logger = logging.getLogger(__name__)


async def mcp_kb_search(params: dict[str, Any]) -> dict[str, Any]:
    """Search the Knowledge Base for remediation guidance using Vertex AI Vector Search.

    Args:
        params: Must contain "query" (str). Optionally "top_k" (int, default 5).
    """
    query = params.get("query")
    if not query:
        return {"error": "Missing required parameter 'query'"}

    top_k = params.get("top_k", 5)
    try:
        top_k = int(top_k)
    except ValueError:
        top_k = 5

    try:
        results = await vector_search(query, top_k=top_k)
        if not results:
            return {"status": "success", "results": [], "message": "No matching KB cards found."}
        
        return {
            "status": "success",
            "results": results,
        }
    except Exception as exc:
        logger.error("mcp_kb_search_error", exc_info=True)
        return {"error": f"Failed to search Knowledge Base: {str(exc)}"}


async def mcp_kb_get_card(params: dict[str, Any]) -> dict[str, Any]:
    """Retrieve a specific Knowledge Base Fix Card by its CWE ID.

    Args:
        params: Must contain "cwe_id" (int or str).
    """
    cwe_id_raw = params.get("cwe_id")
    if not cwe_id_raw:
        return {"error": "Missing required parameter 'cwe_id'"}

    try:
        cwe_id = int(str(cwe_id_raw).replace("CWE-", ""))
    except ValueError:
        return {"error": f"Invalid cwe_id format: {cwe_id_raw}. Must be an integer."}

    try:
        card = await get_fix_card(cwe_id)
        if not card:
            return {"error": f"No Fix Card found for CWE-{cwe_id}."}

        # Convert the Pydantic model to a dict, excluding generated metadata if preferred, or just return everything
        return {
            "status": "success",
            "card": {
                "cwe_id": card.cwe_id,
                "title": card.title,
                "summary": card.summary,
                "content": card.content,
                "fix_steps_json": card.fix_steps_json,
                "tags": card.tags,
                "source": card.source,
            }
        }
    except Exception as exc:
        logger.error("mcp_kb_get_card_error", exc_info=True)
        return {"error": f"Failed to retrieve KB card: {str(exc)}"}
