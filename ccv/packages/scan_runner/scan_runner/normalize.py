"""Normalize raw Veracode findings into internal FindingDoc Pydantic models."""

from __future__ import annotations

from shared.firestore_models import FindingDoc
from shared.logging import get_logger
from shared.utils import generate_uuid, stable_fingerprint

logger = get_logger(__name__)


def normalize_findings(scan_id: str, raw_results: dict) -> list[FindingDoc]:
    """Transform raw Veracode results into FindingDoc instances.

    Supports:
    - Findings REST API v2 envelope: { "_embedded": { "findings": [...] } }
    - MCP wrapper: { "findings": [...] }
    - Direct list
    """
    items = raw_results.get("_embedded", {}).get("findings", [])
    if not items:
        items = raw_results.get("findings", [])
    if not items and isinstance(raw_results, list):
        items = raw_results

    findings: list[FindingDoc] = []
    severity_map = {0: "Informational", 1: "Very Low", 2: "Low", 3: "Medium", 4: "High", 5: "Very High"}

    for item in items:
        details = item.get("finding_details", {})

        cwe_id = int(details.get("cwe", {}).get("id", item.get("cwe_id", 0)))
        severity_num = details.get("severity", item.get("severity", 3))
        severity = (
            severity_map.get(int(severity_num), str(severity_num))
            if isinstance(severity_num, (int, float))
            else str(severity_num)
        )
        title = (
            details.get("finding_category", {}).get("name", "")
            or item.get("title", "Unknown Finding")
        )
        file_path = details.get("file_path", item.get("file_path", "unknown"))
        line = details.get("file_line_number") or item.get("line")

        fp = stable_fingerprint(str(cwe_id), file_path, str(line or ""), title)

        findings.append(FindingDoc(
            id=str(generate_uuid()),
            scan_id=scan_id,
            cwe_id=cwe_id,
            severity=severity,
            title=title,
            file_path=file_path,
            line=int(line) if line else None,
            fingerprint=fp,
            raw_source_json=item,
        ))

    logger.info("findings_normalized", scan_id=scan_id, count=len(findings))
    return findings
