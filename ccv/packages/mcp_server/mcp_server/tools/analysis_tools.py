"""Analysis Agent tools for the MCP server."""

from __future__ import annotations

from typing import Any

from shared.firestore_client import get_firestore_client
from shared.logging import get_logger
from shared.repositories.analysis_store import AnalysisStore
from shared.repositories.finding_store import FindingStore

logger = get_logger(__name__)


async def mcp_request_analysis(params: dict[str, Any]) -> dict[str, Any]:
    """Request a new AI analysis for a specific finding.

    Args:
        params: Must contain "finding_id" (str).
    """
    finding_id = params.get("finding_id")
    if not finding_id:
        return {"error": "Missing required parameter 'finding_id'"}

    db = get_firestore_client()
    finding_store = FindingStore(db)

    finding = await finding_store.get_finding(finding_id)
    if not finding:
        return {"error": f"Finding '{finding_id}' not found in database"}

    try:
        from analysis_agent.agent import analyze_finding
        # Run it synchronously inside the async handler (MCP connection will await it)
        await analyze_finding(finding_id)
        return {
            "status": "success",
            "message": f"Successfully performed AI analysis for finding '{finding_id}'. Use get_finding_analysis to retrieve the results.",
            "finding_id": finding_id,
        }
    except ImportError:
        logger.error("analysis_agent_module_missing")
        return {"error": "The analysis_agent Python module is not available in the current environment."}
    except Exception as exc:
        logger.error("analysis_fatal_error", exc_info=True)
        return {"error": f"Analysis failed: {str(exc)}"}


async def mcp_get_finding_analysis(params: dict[str, Any]) -> dict[str, Any]:
    """Retrieve an existing AI analysis for a specific finding.

    Args:
        params: Must contain "finding_id" (str).
    """
    finding_id = params.get("finding_id")
    if not finding_id:
        return {"error": "Missing required parameter 'finding_id'"}

    db = get_firestore_client()
    analysis_store = AnalysisStore(db)

    analysis = await analysis_store.get_by_finding_id(finding_id)
    if not analysis:
        return {
            "error": f"No AI analysis found for finding '{finding_id}'. You may need to request one first using request_finding_analysis."
        }

    return {
        "finding_id": analysis.finding_id,
        "root_cause": analysis.root_cause,
        "risk": analysis.risk,
        "fix_guidance": analysis.fix_guidance,
        "confidence": analysis.confidence,
        "references": analysis.references_json,
    }
