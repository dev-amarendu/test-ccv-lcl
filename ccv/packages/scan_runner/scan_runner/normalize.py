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
    if not items and isinstance(raw_results, dict) and "flaws" in raw_results:
        items = raw_results["flaws"]

    findings: list[FindingDoc] = []
    seen_fingerprints = set()
    severity_int_map = {
        0: "info", 1: "low", 2: "low", 3: "medium", 4: "high", 5: "high",
    }

    for item in items:
        details = item.get("finding_details", {})

        cwe_id = int(details.get("cwe", {}).get("id", item.get("cwe_id", item.get("cweid", 0))))
        
        raw_sev = details.get("severity", item.get("severity", 3))
        if isinstance(raw_sev, (int, float)) or (isinstance(raw_sev, str) and raw_sev.isdigit()):
            severity = severity_int_map.get(int(raw_sev), "medium")
        else:
            sev_str = str(raw_sev).lower()
            if sev_str == "informational":
                severity = "info"
            elif sev_str == "very low":
                severity = "low"
            elif sev_str == "very high":
                severity = "high"
            elif sev_str not in ("critical", "high", "medium", "low", "info"):
                severity = "medium"
            else:
                severity = sev_str
        title = (
            details.get("finding_category", {}).get("name")
            or details.get("cwe", {}).get("name")
            or item.get("categoryname")
            or item.get("title")
            or details.get("title")
            or item.get("description", "")[:100]
            or details.get("component_filename")
            or "Unknown Finding"
        )
        file_path = details.get("file_path", item.get("file_path", item.get("sourcefile", "unknown")))
        line = details.get("file_line_number") or item.get("line")

        fp = stable_fingerprint(str(cwe_id), file_path, str(line or ""), title)

        if fp in seen_fingerprints:
            continue
        seen_fingerprints.add(fp)

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
