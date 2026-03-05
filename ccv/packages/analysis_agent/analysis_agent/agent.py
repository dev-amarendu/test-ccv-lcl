"""CCV Analysis Agent — powered by Google Agent Development Kit (ADK).

The agent uses Vertex AI Gemini as its LLM and has access to a KB
lookup tool for grounding its analysis with internal remediation
knowledge.

Architecture (GCP-native):
    ┌────────────────┐     ┌────────────────────────────────┐
    │  Cloud Pub/Sub  │────▶│  /pubsub/analyze-finding       │
    │  (push)         │     │    ↓                            │
    └────────────────┘     │  analyze_finding()               │
                           │    ↓                            │
                           │  ADK Runner.run_async()          │
                           │    ↓                            │
                           │  ┌──────────────────────────┐   │
                           │  │  ADK Agent                │   │
                           │  │  model: Gemini            │   │
                           │  │  tools: [lookup_kb_card]  │   │
                           │  │  instruction: analyst     │   │
                           │  └──────────────────────────┘   │
                           │    ↓                            │
                           │  Parse JSON → store analysis    │
                           └────────────────────────────────┘

Usage (CLI debug):
    python -m analysis_agent.agent --finding-id <uuid>
"""

from __future__ import annotations

import argparse
import asyncio
import os
import uuid

from shared.config import get_settings
from shared.firestore_client import get_firestore_client
from shared.firestore_models import AuditLogDoc, FindingAnalysisDoc, FindingDoc
from shared.logging import get_logger, set_request_id, setup_logging
from shared.repositories.analysis_store import AnalysisStore
from shared.repositories.audit_store import AuditStore
from shared.repositories.finding_store import FindingStore
from shared.utils import generate_uuid

from analysis_agent.prompts import AGENT_INSTRUCTION, parse_analysis_response
from analysis_agent.tools import lookup_kb_fix_card

logger = get_logger(__name__)


# ── Vertex AI / ADK environment setup ─────────────────────────────────────────


def _ensure_vertex_env() -> None:
    """Set env vars required by google-genai / ADK for Vertex AI mode."""
    settings = get_settings()
    os.environ.setdefault("GOOGLE_CLOUD_PROJECT", settings.google_cloud_project)
    os.environ.setdefault("GOOGLE_CLOUD_LOCATION", settings.google_cloud_location)
    os.environ.setdefault(
        "GOOGLE_GENAI_USE_VERTEXAI",
        str(settings.google_genai_use_vertexai).lower(),
    )


# ── ADK Agent factory ─────────────────────────────────────────────────────────


def _create_analysis_agent():
    """Create and return the ADK Agent for vulnerability analysis."""
    from google.adk.agents import Agent

    settings = get_settings()
    _ensure_vertex_env()

    agent = Agent(
        model=settings.llm_model,
        name="ccv_vulnerability_analyst",
        description=(
            "Analyses SAST security findings and produces structured "
            "root-cause analysis, risk assessment, and remediation guidance."
        ),
        instruction=AGENT_INSTRUCTION,
        tools=[lookup_kb_fix_card],
    )
    return agent


# ── ADK Runner execution ──────────────────────────────────────────────────────


async def _run_agent_for_finding(finding: FindingDoc) -> str:
    """Run the ADK agent for a single finding and return raw text response."""
    from google.adk.runners import Runner
    from google.adk.sessions import InMemorySessionService
    from google.genai import types

    agent = _create_analysis_agent()
    session_service = InMemorySessionService()
    runner = Runner(
        agent=agent,
        app_name="ccv_analysis_agent",
        session_service=session_service,
    )

    session_id = uuid.uuid4().hex
    await session_service.create_session(
        app_name="ccv_analysis_agent",
        user_id="ccv_system",
        session_id=session_id,
    )

    user_prompt = _build_finding_message(finding)
    content = types.Content(
        role="user",
        parts=[types.Part(text=user_prompt)],
    )

    final_text = ""
    events = runner.run_async(
        user_id="ccv_system",
        session_id=session_id,
        new_message=content,
    )
    async for event in events:
        if event.is_final_response() and event.content and event.content.parts:
            final_text = event.content.parts[0].text or ""

    if not final_text:
        raise RuntimeError("ADK agent returned empty response")

    logger.info(
        "adk_agent_response",
        finding_id=finding.id,
        response_chars=len(final_text),
    )
    return final_text


def _build_finding_message(finding: FindingDoc) -> str:
    """Build a user message describing a finding for the ADK agent."""
    parts = ["Please analyse the following SAST finding:\n"]
    parts.append(f"CWE: CWE-{finding.cwe_id}")
    parts.append(f"Severity: {finding.severity}")
    parts.append(f"Title: {finding.title}")
    parts.append(f"File: {finding.file_path}")
    if finding.line:
        parts.append(f"Line: {finding.line}")

    # Prefer explicit code snippet if present
    snippet = None
    if finding.code_snippet_json:
        snippet = finding.code_snippet_json.get("snippet", "")

    # Fallback: try to extract snippet from raw_source_json (vendor payload)
    if not snippet and finding.raw_source_json:
        # common vendor keys that might contain snippet text
        snippet = (
            finding.raw_source_json.get("code_snippet")
            or finding.raw_source_json.get("snippet")
            or finding.raw_source_json.get("finding_details", {}).get("snippet")
        )

    # Fallback 2: if finding references a GCS raw SCA blob, download and extract the indexed item
    if not snippet and getattr(finding, "gcs_ref", None):
        try:
            from google.cloud import storage
            import json

            gcs_ref = finding.gcs_ref
            uri = gcs_ref.get("uri")
            idx = gcs_ref.get("index_in_blob")
            if uri and idx is not None:
                # Simple synchronous download in a thread to avoid blocking event loop
                async def _download_and_extract():
                    def _download():
                        parts = uri.replace("gs://", "").split("/", 1)
                        bucket_name, blob_name = parts[0], parts[1]
                        client = storage.Client()
                        blob = client.bucket(bucket_name).blob(blob_name)
                        raw = blob.download_as_text()
                        return raw

                    raw_text = await asyncio.to_thread(_download)
                    arr = json.loads(raw_text)
                    if isinstance(arr, list) and 0 <= int(idx) < len(arr):
                        item = arr[int(idx)]
                        return (
                            item.get("code_snippet")
                            or item.get("snippet")
                            or item.get("finding_details", {}).get("snippet")
                        )
                    return None

                snippet = asyncio.get_event_loop().run_until_complete(_download_and_extract())
        except Exception:
            logger.debug("gcs_snippet_fetch_failed", finding_id=finding.id, exc_info=True)

    if snippet:
        parts.append(f"\nCode context:\n```\n{snippet}\n```")

    return "\n".join(parts)


# ── Core analysis logic ───────────────────────────────────────────────────────


async def analyze_finding(finding_id: str) -> None:
    """Analyse a single finding: invoke ADK agent, store result in Firestore."""
    settings = get_settings()
    db = get_firestore_client()
    rid = uuid.uuid4().hex[:16]
    set_request_id(rid)

    finding_store = FindingStore(db)
    analysis_store = AnalysisStore(db)
    audit_store = AuditStore(db)

    finding = await finding_store.get_finding(finding_id)
    if not finding:
        logger.error("finding_not_found", finding_id=finding_id)
        return

    # Idempotency: skip if analysis already exists
    existing = await analysis_store.get_by_finding_id(finding_id)
    if existing:
        logger.info("analysis_already_exists", finding_id=finding_id)
        return

    # Ensure we have a code snippet for context: try raw_source_json, otherwise fetch from GCS if referenced.
    if not finding.code_snippet_json or not finding.code_snippet_json.get("snippet"):
        # Attempt to extract small snippet from raw_source_json
        snippet = None
        if finding.raw_source_json:
            snippet = (
                finding.raw_source_json.get("code_snippet")
                or finding.raw_source_json.get("snippet")
                or finding.raw_source_json.get("finding_details", {}).get("snippet")
            )
        # If still not found and we have a gcs_ref, download the SCA blob and extract by index
        if not snippet and getattr(finding, "gcs_ref", None):
            try:
                from google.cloud import storage
                import json

                gcs_ref = finding.gcs_ref
                uri = gcs_ref.get("uri")
                idx = gcs_ref.get("index_in_blob")
                if uri and idx is not None:
                    def _download():
                        parts = uri.replace("gs://", "").split("/", 1)
                        bucket_name, blob_name = parts[0], parts[1]
                        client = storage.Client()
                        blob = client.bucket(bucket_name).blob(blob_name)
                        return blob.download_as_text()

                    raw_text = await asyncio.to_thread(_download)
                    arr = json.loads(raw_text)
                    if isinstance(arr, list) and 0 <= int(idx) < len(arr):
                        item = arr[int(idx)]
                        snippet = (
                            item.get("code_snippet")
                            or item.get("snippet")
                            or item.get("finding_details", {}).get("snippet")
                        )
            except Exception:
                logger.debug("gcs_snippet_fetch_failed", finding_id=finding.id, exc_info=True)

        if snippet:
            finding.code_snippet_json = {"snippet": snippet}

    # ── Run the ADK Agent ─────────────────────────────────────────────────
    logger.info("adk_agent_starting", finding_id=finding_id)
    raw_response = await _run_agent_for_finding(finding)

    output = parse_analysis_response(raw_response)

    # ── Persist analysis ──────────────────────────────────────────────────
    analysis = FindingAnalysisDoc(
        id=str(generate_uuid()),
        finding_id=finding_id,
        model_name=settings.llm_model,
        model_version="adk-v1",
        root_cause=output.root_cause,
        risk=output.risk,
        fix_guidance=output.fix_guidance,
        code_snippet=output.code_snippet,
        references_json={"cwe_references": output.cwe_references},
        provenance_json={
            "framework": "google-adk",
            "agent_name": "ccv_vulnerability_analyst",
            "kb_tool_available": True,
        },
        confidence=0.85,
    )
    await analysis_store.create_analysis(analysis)

    # Update finding enrichment columns
    await finding_store.update_finding(finding_id, {
        "enrichment_summary": output.root_cause[:200],
        "enrichment_confidence": 0.85,
    })

    await audit_store.log_entry(AuditLogDoc(
        request_id=rid,
        actor="analysis_agent_adk",
        action="analyze_finding",
        entity_type="finding",
        entity_id=finding_id,
        status="completed",
        details_json={
            "framework": "google-adk",
            "model": settings.llm_model,
        },
    ))

    logger.info(
        "finding_analyzed",
        finding_id=finding_id,
        framework="google-adk",
    )


# ── CLI entry-point ───────────────────────────────────────────────────────────


def main() -> None:
    setup_logging(get_settings().api_log_level)

    parser = argparse.ArgumentParser(description="CCV Analysis Agent (ADK)")
    parser.add_argument(
        "--finding-id", type=str, help="Analyse a specific finding"
    )
    args = parser.parse_args()

    if args.finding_id:
        asyncio.run(analyze_finding(args.finding_id))
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
