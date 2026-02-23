"""Agent instruction and response validation for the CCV Analysis Agent.

``AGENT_INSTRUCTION`` is used as the ADK Agent's ``instruction`` parameter.
``AnalysisOutput`` validates the structured JSON the agent produces.
"""

from __future__ import annotations

import json

from pydantic import BaseModel, ValidationError

from shared.logging import get_logger

logger = get_logger(__name__)


# ── Output schema ─────────────────────────────────────────────────────────────


class AnalysisOutput(BaseModel):
    """Expected JSON output from the ADK agent."""

    root_cause: str
    risk: str
    fix_guidance: str
    cwe_references: list[str] = []


# ── ADK Agent instruction ────────────────────────────────────────────────────


AGENT_INSTRUCTION = """\
You are a senior application security analyst working within the CCV \
(Centralized Code Vulnerability) platform. Your job is to analyse SAST \
(Static Application Security Testing) findings and produce structured \
remediation guidance.

WORKFLOW:
1. Read the finding details provided in the user message.
2. ALWAYS call the 'lookup_kb_fix_card' tool with the finding's CWE ID \
   to retrieve internal remediation guidance from the knowledge base.
3. Combine your security expertise with any KB Fix Card content retrieved \
   to produce your analysis.
4. Return your analysis as a single JSON object (no markdown fences, no \
   extra text outside the JSON).

OUTPUT JSON SCHEMA:
{
  "root_cause": "string — technical explanation of why this vulnerability exists",
  "risk": "string — business and security risk if exploited",
  "fix_guidance": "string — step-by-step remediation guidance (no code patches)",
  "cwe_references": [
    "string — CWE-ID and title, e.g. CWE-79: Improper Neutralization …"
  ]
}

RULES:
- Output ONLY valid JSON matching the schema above.
- Be specific: reference the exact CWE, file path, and code context provided.
- Do NOT generate code patches or diffs.
- Do NOT make policy decisions (pass/fail).
- Keep each field concise (under 500 words).
- If the KB Fix Card was found, incorporate its guidance into fix_guidance \
  and note it was grounded in the knowledge base.
- If no KB Fix Card was found, rely on your own expertise and note that no \
  internal KB card was available.
"""


# ── Response validation ───────────────────────────────────────────────────────


def parse_analysis_response(raw_text: str) -> AnalysisOutput:
    """Parse and validate the ADK agent's JSON response.

    Handles markdown code fences in case the model wraps its output.
    """
    text = raw_text.strip()

    # Strip markdown code fences if present
    if text.startswith("```"):
        lines = text.split("\n")
        if lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        text = "\n".join(lines)

    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        logger.error("analysis_json_parse_error", raw=text[:200], error=str(exc))
        raise ValueError(f"Agent response is not valid JSON: {exc}") from exc

    try:
        return AnalysisOutput.model_validate(data)
    except ValidationError as exc:
        logger.error("analysis_validation_error", data=data, error=str(exc))
        raise ValueError(f"Agent response does not match schema: {exc}") from exc
