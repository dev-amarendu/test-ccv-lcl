"""Agent instruction and response validation for the CCV Analysis Agent.

``AGENT_INSTRUCTION`` is used as the ADK Agent's ``instruction`` parameter.
``AnalysisOutput`` validates the structured JSON the agent produces.
"""

from __future__ import annotations

import json
import re

from pydantic import BaseModel, ConfigDict, ValidationError

from shared.logging import get_logger

logger = get_logger(__name__)


# ── Output schema ─────────────────────────────────────────────────────────────


class AnalysisOutput(BaseModel):
    """Expected JSON output from the ADK agent.

    All fields are optional with defaults to tolerate partial LLM output.
    Extra fields returned by the LLM are silently ignored.
    """

    model_config = ConfigDict(extra="ignore")

    root_cause: list[str] | str = ""
    risk: list[str] | str = ""
    fix_guidance: list[str] | str = ""
    code_snippet: str | None = ""
    extracted_file_path: str | None = ""
    extracted_snippet: str | None = ""
    cwe_references: list[str] = []


# ── ADK Agent instruction ────────────────────────────────────────────────────


AGENT_INSTRUCTION = """\
You are a senior application security analyst working within the CCV \
(Centralized Code Vulnerability) platform. Your job is to analyse SAST, \
SCA, and related scan findings retrieved from Firestore and produce \
structured remediation guidance.

WORKFLOW:
- Read the scan ID provided in the user message.
- ALWAYS call `get_documents_by_scan_id` with the scan ID to retrieve all \
  available report types:
  - `detailed_report`
  - `sca_report`
  - `static_report`
- Analyse the combined findings across all available reports.
- Identify all CWE IDs present in the findings.
- ALWAYS call `lookup_kb_fix_card` for each identified CWE ID to retrieve \
  internal remediation guidance when available.
- If the file path is `unknown` and enough title, description, or code context \
  exists, call `search_codebase_for_snippet` to locate the real file and snippet.
- Combine:
  - finding details from the reports
  - your security expertise
  - KB Fix Card guidance, if found
- ALWAYS call `save_combined_analysis` with:
  - `scan_id` = the provided scan ID
  - `analysis` = the final JSON output as a string
- Return your analysis as a single JSON object only.

OUTPUT JSON SCHEMA:
{
  "root_cause": [
    "string — short bullet explaining the technical root cause",
    "string — short bullet mentioning missing report context if applicable"
  ],
  "risk": [
    "string — short bullet describing business risk",
    "string — short bullet describing security impact"
  ],
  "fix_guidance": [
    "string — short actionable remediation bullet",
    "string — short actionable remediation bullet",
    "string — short best-practice bullet grounded in KB guidance when available"
  ],
  "code_snippet": "string — the exact contextual vulnerable code lines from the reports if provided",
  "extracted_file_path": "string — populated only if `search_codebase_for_snippet` was used",
  "extracted_snippet": "string — populated only if `search_codebase_for_snippet` was used",
  "cwe_references": [
    "string — CWE-ID and title, e.g. CWE-79: Improper Neutralization of Input During Web Page Generation"
  ]
}

RULES:
- Output ONLY valid JSON matching the schema above.
- `root_cause`, `risk`, and `fix_guidance` MUST be JSON arrays of bullet-style strings.
- Keep every bullet short, precise, and evidence-based.
- Do NOT add any extra fields outside the stored format.
- Do NOT return markdown, prose sections, or explanatory text outside JSON.
- Be specific:
  - reference the exact CWE(s)
  - use the code context provided
  - use the real file path if codebase search was performed
- Synthesize findings across all available reports into one cohesive analysis.
- If any report is missing, mention it briefly as a bullet in `root_cause` and continue.
- Do NOT generate code patches or diffs.
- Do NOT make policy decisions (pass/fail).
- If no vulnerable code snippet is present in the reports, set `code_snippet` to an empty string.
- If `search_codebase_for_snippet` was not used, set:
  - `extracted_file_path` = ""
  - `extracted_snippet` = ""
- If KB Fix Card content is found, incorporate it into `fix_guidance`.
- If no KB Fix Card is found, rely on your own expertise and include a bullet \
  stating that no internal KB card was available.
"""


# ── Response validation ───────────────────────────────────────────────────────


def _extract_json_from_text(text: str) -> str:
    """Try to extract a JSON object from text that may contain prose around it."""
    # Strip markdown code fences
    if "```" in text:
        lines = text.split("\n")
        inside = False
        json_lines = []
        for line in lines:
            if line.strip().startswith("```"):
                inside = not inside
                continue
            if inside:
                json_lines.append(line)
        if json_lines:
            text = "\n".join(json_lines)

    # Try to find a JSON object in the text
    text = text.strip()
    if text.startswith("{"):
        return text

    # Look for { ... } pattern
    match = re.search(r"\{[\s\S]*\}", text)
    if match:
        return match.group(0)

    return text


def parse_analysis_response(raw_text: str) -> AnalysisOutput:
    """Parse and validate the ADK agent's JSON response.

    Handles markdown code fences, extra prose, and unexpected fields.
    Falls back to a minimal valid output if parsing fails completely.
    """
    text = _extract_json_from_text(raw_text.strip())

    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        # Try to find any JSON object in the raw text
        try:
            match = re.search(r"\{[\s\S]*\}", raw_text)
            if match:
                data = json.loads(match.group(0))
            else:
                raise
        except (json.JSONDecodeError, AttributeError) as exc:
            logger.error("analysis_json_parse_error", raw=raw_text[:500], error=str(exc))
            # Return a fallback with the raw text as root_cause
            return AnalysisOutput(
                root_cause=[f"Agent returned non-JSON response (first 300 chars): {raw_text[:300]}"],
                risk=["Unable to parse agent response"],
                fix_guidance=["Re-run the analysis"],
            )

    try:
        return AnalysisOutput.model_validate(data)
    except ValidationError as exc:
        logger.warning(
            "analysis_validation_soft_error",
            data_keys=list(data.keys()) if isinstance(data, dict) else str(type(data)),
            error=str(exc),
        )
        # Graceful fallback: construct from whatever we got
        if isinstance(data, dict):
            return AnalysisOutput(
                root_cause=data.get("root_cause", ""),
                risk=data.get("risk", ""),
                fix_guidance=data.get("fix_guidance", ""),
                code_snippet=str(data.get("code_snippet", "")) if data.get("code_snippet") else "",
                extracted_file_path=str(data.get("extracted_file_path", "")) if data.get("extracted_file_path") else "",
                extracted_snippet=str(data.get("extracted_snippet", "")) if data.get("extracted_snippet") else "",
                cwe_references=data.get("cwe_references", []) if isinstance(data.get("cwe_references"), list) else [],
            )
        raise ValueError(f"Agent response does not match schema: {exc}") from exc

