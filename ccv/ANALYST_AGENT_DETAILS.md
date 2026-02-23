# Analyst Agent Details

Purpose
-------
This document describes the data shapes, inputs, outputs, and runtime behavior of the CCV Analysis Agent (ADK-based). It is intended for developers who implement, test, or operate the agent.

Location of relevant code
-------------------------
- Agent implementation: `ccv/packages/analysis_agent/analysis_agent/agent.py`
- Agent tools (KB lookup): `ccv/packages/analysis_agent/analysis_agent/tools.py`
- Firestore document models: `ccv/packages/shared/shared/firestore_models.py`
- API schemas (responses): `ccv/packages/shared/shared/schemas.py`
- Stores/repositories: `ccv/packages/shared/shared/repositories/*`

Primary models used
-------------------
1) FindingDoc (input)

Key fields consumed:
- `id` (string)  
- `scan_id` (string)  
- `cwe_id` (int)  
- `severity` (string)  
- `title` (string)  
- `file_path` (string)  
- `line` (int | null)  
- `code_snippet_json` (dict, optional) — agent uses `code_snippet_json["snippet"]` when present  
- `raw_source_json` (dict, optional) — kept for provenance but not always sent to LLM

Source: `FindingDoc` in `firestore_models.py`

2) KBFixCardDoc (KB lookup)

Key fields:
- `id`, `cwe_id`, `title`, `content`, `tags`  
- `embedding` is present in the model but is not stored in Firestore (embeddings are managed in Vertex AI Vector Search). See `to_firestore_dict()` behavior.

3) FindingAnalysisDoc (output)

Fields written by the agent:
- `id` (string)  
- `finding_id` (string)  
- `model_name` (string)  
- `model_version` (string)  
- `root_cause` (string)  
- `risk` (string)  
- `fix_guidance` (string)  
- `references_json` (dict, optional)  
- `provenance_json` (dict, optional)  
- `confidence` (float, optional)  
- `created_at`, `updated_at` (timestamps)

Source: `FindingAnalysisDoc` in `firestore_models.py`

API schema used to expose results
---------------------------------
- `FindingAnalysisResponse` in `shared/schemas.py` maps the Firestore `FindingAnalysisDoc` to API responses.

Agent behavior / runtime flow
----------------------------
1. Receiver (Pub/Sub or CLI) supplies a `finding_id` to the agent handler `analyze_finding(finding_id)`.  
2. Agent reads the finding from Firestore via `FindingStore.get_finding(finding_id)` and validates existence.  
3. Idempotency: agent checks `AnalysisStore.get_by_finding_id(finding_id)` and returns early if analysis exists.  
4. Build LLM prompt from `FindingDoc`:
   - CWE, severity, title, file path, optional line
   - include code snippet block when available:

   Example prompt fragment:

   ```
   Please analyse the following SAST finding:

   CWE: CWE-<cwe_id>
   Severity: <severity>
   Title: <title>
   File: <file_path>
   Line: <line>         # optional

   Code context:
   ```
   <snippet>
   ```
   ```

5. Agent may call KB lookup tool (`lookup_kb_fix_card(cwe_id)`) to ground analysis with curated remediation content:
   - Primary: call KB microservice (`KB Service`) via HTTP.
   - Fallback: direct Firestore query of `kb_fix_cards` collection.
   - If a fix card is found, include its summary/content as additional context for the LLM.

6. Run ADK agent / LLM with the constructed prompt (ADK Runner). Stream and collect final response text.  
7. Parse ADK response into structured analysis (root cause, risk, fix guidance, references).  
8. Persist new `FindingAnalysisDoc` via `AnalysisStore.create_analysis()`.  
9. Update `FindingDoc` enrichment fields (`enrichment_summary`, `enrichment_confidence`) via `FindingStore.update_finding()`.  
10. Emit audit log entry via `AuditStore.log_entry()`.

Operational contracts and guarantees
-----------------------------------
- Idempotency: rely on `finding_id` lookup in `finding_analyses` (no DB unique constraint). Consider deterministic analysis ID (e.g., uuid5) for stronger idempotency if required.  
- Atomicity: writes to analysis and finding enrichment are separate ops. If strict atomicity is required, consider a transaction pattern or tolerate temporary divergence.  
- Retries & DLQ: Pub/Sub push handlers should use standard retry/backoff and dead-letter topics for failed analyses. The agent itself should be robust to transient Vertex/HTTP/GC failures.

Where vectors/embeddings live
-----------------------------
- KB embeddings are stored/upserted into Vertex AI Vector Search (managed index).  
- Firestore `KBFixCardDoc` model contains `embedding` in memory but `to_firestore_dict()` removes `embedding` before writing — the production vector index is in Vertex. See `KBFixCardDoc.to_firestore_dict()`.

CLI / debugging
----------------
- The agent supports a CLI mode for single-run debugging:
  - `python -m analysis_agent.agent --finding-id <uuid>`
- This executes `analyze_finding()` for the given finding id and writes results to Firestore (same code path as Pub/Sub handling).

Example JSON (input)
--------------------
{
  "id": "f-1234",
  "scan_id": "s-1111",
  "cwe_id": 89,
  "severity": "High",
  "title": "SQL Injection",
  "file_path": "src/db.py",
  "line": 42,
  "fingerprint": "abc123",
  "code_snippet_json": {"snippet": "cursor.execute('...'+ user_input)"},
  "raw_source_json": {...}
}

Example JSON (analysis output)
------------------------------
{
  "id": "a-5678",
  "finding_id": "f-1234",
  "model_name": "gemini-1.5-pro",
  "model_version": "adk-v1",
  "root_cause": "User input concatenated into SQL without parameterization",
  "risk": "Data exfiltration and privilege escalation",
  "fix_guidance": "Use parameterized queries / prepared statements; validate input",
  "confidence": 0.85,
  "created_at": "2026-02-19T12:00:00Z"
}

Recommendations & TODOs
-----------------------
- Consider deterministic document IDs for analyses to avoid duplicate writes during concurrency.  
- Add monitoring on analysis counts, Pub/Sub retry rates, and Vertex latency.  
- Improve fallbacks for KB lookup: cache recent KB responses locally to reduce latency and Vertex/API calls.  
- Add unit tests for prompt building and integration tests that mock ADK/LLM responses.

References
----------
- `ccv/packages/analysis_agent/analysis_agent/agent.py` — prompt builder, execution, persistence flow.  
- `ccv/packages/analysis_agent/analysis_agent/tools.py` — KB lookup tool and Firestore fallback.  
- `ccv/packages/shared/shared/firestore_models.py` — `FindingDoc`, `FindingAnalysisDoc`, `KBFixCardDoc` definitions.

