# CCV Migration: PostgreSQL → All-GCP Serverless Stack

> **Goal**: Fully replace PostgreSQL (+ pgvector + Alembic + SQL job queue) with a **100% GCP-native serverless stack**:
> - **Firestore** — document store (replaces all 12 Postgres tables)
> - **Cloud Pub/Sub** — managed message queue (replaces SQL `FOR UPDATE SKIP LOCKED` job pattern)
> - **Cloud Scheduler** — periodic triggers (replaces `asyncio.sleep()` poller loops)
> - **Vertex AI Vector Search** — embedding similarity search (replaces pgvector)

---

## Architecture: Before & After

```
BEFORE (Postgres-centric)                    AFTER (All-GCP Serverless)
─────────────────────────                    ─────────────────────────
┌────────────────────┐                       ┌────────────────────┐
│ PostgreSQL+pgvector│                       │ Firestore          │
│ • 12 tables        │          ──▶          │ • 12 collections   │
│ • SQL job queue    │                       └────────────────────┘
│ • pgvector RAG     │                       ┌────────────────────┐
│ • Alembic migrate  │                       │ Cloud Pub/Sub      │
└────────────────────┘                       │ • Push-based queue │
┌────────────────────┐                       └────────────────────┘
│ asyncio.sleep loop │          ──▶          ┌────────────────────┐
│ (Veracode poller)  │                       │ Cloud Scheduler    │
└────────────────────┘                       │ • Cron triggers    │
                                             └────────────────────┘
                                             ┌────────────────────┐
                                             │ Vertex AI Vector   │
                                             │ Search (RAG)       │
                                             └────────────────────┘
```

---

## PHASE 0 — GCP Infrastructure & Configuration

### 0.1 GCP Project Setup
- [ ] Enable Firestore API → create Firestore database (Native mode) in target region
- [ ] Enable Cloud Pub/Sub API → create topics:
  - `ccv-analyze-finding` (for analysis jobs)
  - `ccv-run-scan` (for scan jobs)
  - `ccv-sync-veracode` (for Veracode sync)
  - `ccv-embed-kb` (for KB embedding)
- [ ] Create push subscriptions for each topic → point to API handler endpoints
- [ ] Enable Cloud Scheduler API
- [ ] Enable Vertex AI API → create a Vector Search index + deploy endpoint
- [ ] Set up IAM service account with roles: `roles/datastore.user`, `roles/pubsub.publisher`, `roles/pubsub.subscriber`, `roles/aiplatform.user`
- [ ] Configure Application Default Credentials (ADC) for local development

### 0.2 Local Development Environment
- [ ] Add Firestore emulator to dev workflow (`gcloud emulators firestore start`)
- [ ] Update `docker-compose.yml` — remove `postgres` service and `pgdata` volume
- [ ] Delete `init-db.sql` (no longer needed)
- [ ] For Pub/Sub local dev: use Pub/Sub emulator (`gcloud beta emulators pubsub start`) or a direct-call wrapper in `BACKEND_MOCK_MODE`

### 0.3 Update Dependencies
**Remove** (from `requirements.txt` + `packages/shared/pyproject.toml` + `packages/kb_service/pyproject.toml`):
- [ ] `sqlalchemy[asyncio]`, `asyncpg`, `psycopg2-binary`, `pgvector`, `alembic`, `aiosqlite`

**Add**:
- [ ] `google-cloud-firestore` — Firestore client
- [ ] `google-cloud-pubsub` — Pub/Sub publisher + subscriber client
- [ ] `google-cloud-scheduler` — Cloud Scheduler client (optional, config via `gcloud`)
- [ ] `google-cloud-aiplatform` — Vertex AI Vector Search client

### 0.4 Update Configuration
**File: `shared/config.py`**
- [ ] Remove: `postgres_dsn`, `postgres_dsn_sync`, `enable_pgvector_index`, `pgvector_index_type`
- [ ] Add: `firestore_project_id`, `firestore_database` (default `"(default)"`)
- [ ] Add: `pubsub_project_id`
- [ ] Add: topic names: `pubsub_topic_analyze_finding`, `pubsub_topic_run_scan`, `pubsub_topic_sync_veracode`, `pubsub_topic_embed_kb`
- [ ] Add: `vector_search_index_endpoint`, `vector_search_index_id`, `vector_search_deployed_index_id`

**File: `.env.example`**
- [ ] Remove all `POSTGRES_*` variables
- [ ] Add `FIRESTORE_PROJECT_ID`, `FIRESTORE_DATABASE`
- [ ] Add `PUBSUB_PROJECT_ID`, `PUBSUB_TOPIC_ANALYZE_FINDING`, `PUBSUB_TOPIC_RUN_SCAN`, `PUBSUB_TOPIC_SYNC_VERACODE`, `PUBSUB_TOPIC_EMBED_KB`
- [ ] Add `VECTOR_SEARCH_INDEX_ENDPOINT`, `VECTOR_SEARCH_INDEX_ID`, `VECTOR_SEARCH_DEPLOYED_INDEX_ID`

---

## PHASE 1 — Firestore Data Layer (Replace SQLAlchemy ORM)

### 1.1 Design Firestore Collection Schema
- [ ] Map all 12 SQL tables to Firestore collections:

| SQL Table | Firestore Collection | Document ID | Key Indexes |
|-----------|---------------------|-------------|-------------|
| `organizations` | `organizations` | UUID string | — |
| `repos` | `repos` | UUID string | `org_id`, `connected` |
| `scans` | `scans` | UUID string | `repo_id`, `status`, `external_build_id`, `created_at` |
| `scan_artifacts` | `scans/{scanId}/artifacts` | UUID string | (subcollection) |
| `findings` | `findings` | UUID string | `scan_id`, `cwe_id`, `severity`, `fingerprint` |
| `finding_analysis` | `finding_analyses` | UUID string | `finding_id` (unique) |
| `schedules` | `schedules` | UUID string | `repo_id`, `enabled`, `next_run_at` |
| `jobs` | *(Cloud Pub/Sub — no collection needed)* | — | — |
| `veracode_sync_state` | `sync_state` | `"veracode"` (singleton) | — |
| `kb_fix_cards` | `kb_fix_cards` | UUID string | `cwe_id` (unique) |
| `audit_logs` | `audit_logs` | auto-ID | `created_at` |
| `users` | `users` | UUID string | `email` (unique) |

- [ ] Document denormalization decisions (e.g., embed `repo_name` in scan docs for display)
- [ ] Create Firestore composite indexes for multi-field queries

### 1.2 Create Firestore Client Module
**File: `packages/shared/shared/firestore_client.py`** *(NEW)*
- [ ] Async Firestore client singleton: `get_firestore_client() -> AsyncClient`
- [ ] Support Firestore emulator via `FIRESTORE_EMULATOR_HOST` env var
- [ ] FastAPI dependency: `get_db()` returns Firestore client

### 1.3 Create Firestore Data Models
**File: `packages/shared/shared/firestore_models.py`** *(NEW)*
- [ ] Pydantic models for each collection's document shape
- [ ] `to_firestore_dict()` and `from_firestore_doc()` serialization helpers
- [ ] Handle UUID ↔ string, datetime ↔ Firestore Timestamp conversions

### 1.4 Create Repository Layer
**Directory: `packages/shared/shared/repositories/`** *(NEW — 10 files)*

| File | Store Interface | Key Methods |
|------|---------------|-------------|
| `base.py` | Abstract protocols | Base CRUD signatures |
| `repo_store.py` | `RepoStore` | `list_repos()`, `get_repo()`, `create_repo()`, `update_repo()` |
| `scan_store.py` | `ScanStore` | `create_scan()`, `get_scan()`, `list_scans()`, `update_scan()`, `find_by_build_id()`, `add_artifact()` |
| `finding_store.py` | `FindingStore` | `create_findings()`, `get_finding()`, `list_findings()` (paginated, filterable) |
| `analysis_store.py` | `AnalysisStore` | `create_analysis()`, `get_analysis()`, `update_analysis()` |
| `schedule_store.py` | `ScheduleStore` | Full CRUD + `list_due_schedules(now)` |
| `kb_store.py` | `KBFixCardStore` | `get_by_cwe()`, `upsert()`, `list_cards()`, `increment_usage()` |
| `audit_store.py` | `AuditStore` | `log_entry()`, `list_logs()` |
| `user_store.py` | `UserStore` | CRUD |
| `sync_state_store.py` | `SyncStateStore` | `get_state()`, `update_state()` (single-doc) |

### 1.5 Remove SQLAlchemy Layer
- [ ] **Delete** `shared/db.py` — replaced by `firestore_client.py`
- [ ] **Delete** `shared/models.py` — replaced by `firestore_models.py`
- [ ] **Delete** `packages/api_service/alembic/` directory
- [ ] **Delete** `packages/api_service/alembic.ini`
- [ ] Update `shared/__init__.py` exports

---

## PHASE 2 — Cloud Pub/Sub Job Queue (Replace SQL Job Queue)

### 2.1 Create Pub/Sub Publisher Module
**File: `packages/shared/shared/pubsub_client.py`** *(NEW)*
- [ ] Pub/Sub publisher singleton: `get_publisher() -> PublisherClient`
- [ ] `publish_message(topic, payload)` → publishes JSON message to the appropriate topic
- [ ] Topic mapping:
  - `ANALYZE_FINDING` → topic `ccv-analyze-finding`
  - `RUN_SCAN` → topic `ccv-run-scan`
  - `SYNC_VERACODE` → topic `ccv-sync-veracode`
  - `EMBED_KB` → topic `ccv-embed-kb`
- [ ] Local dev mode: bypass Pub/Sub, call handler directly or use emulator

### 2.2 Create Push Subscription Handler Endpoints
**File: `packages/api_service/api_service/routes/tasks.py`** *(NEW)*
- [ ] `POST /pubsub/analyze-finding` — receives push from Pub/Sub subscription, calls `analyze_finding()`
- [ ] `POST /pubsub/run-scan` — receives push, calls `run_scan_pipeline()`
- [ ] `POST /pubsub/sync-veracode` — receives push, calls `run_sync_once()`
- [ ] `POST /pubsub/embed-kb` — receives push, calls KB embedding logic
- [ ] Parse Pub/Sub push message envelope: `request.json["message"]["data"]` (base64-decoded JSON)
- [ ] Validate Pub/Sub push auth token (OIDC) or verify source
- [ ] Return `200`/`204` on success (acknowledges message), `4xx`/`5xx` to trigger retry
- [ ] Configure dead-letter topic for messages that fail after max retries

### 2.3 Set Up Cloud Scheduler for Periodic Sync
- [ ] Create Cloud Scheduler job: `*/5 * * * *` → publishes message to `ccv-sync-veracode` topic
- [ ] Or: Cloud Scheduler directly calls `POST /pubsub/sync-veracode` on the API
- [ ] This replaces the `scan_runner/poller.py` `asyncio.sleep(300)` loop

### 2.4 Migrate Enqueue Logic
**Replace SQL INSERT with Pub/Sub publish in these files:**
- [ ] `scan_runner/enqueue_analysis.py` — `enqueue_analysis_jobs()` → batch publish to `ccv-analyze-finding` topic
- [ ] `scan_runner/jobs.py` — `enqueue_job()` → `pubsub_client.publish_message()`
- [ ] `scan_runner/jobs.py` — remove `claim_next_job()` and `complete_job()` (no longer needed — Pub/Sub handles delivery + retries)
- [ ] `analysis_agent/jobs.py` — remove `claim_next_analysis_job()` and `complete_analysis_job()` (replaced by push subscription handler)

### 2.5 Refactor Worker Architecture
The worker model fundamentally changes from **pull (polling)** to **push (Pub/Sub delivery)**:

```
BEFORE (Pull model):                    AFTER (Push model):
while True:                              @app.post("/pubsub/analyze-finding")
    job = claim_next_job()  # poll DB    async def handle_analyze(request):
    if job:                                  msg = decode_pubsub_message(request)
        process(job)                         finding_id = msg["finding_id"]
        complete_job(job.id, DONE)            await analyze_finding(finding_id)
    sleep(5)                                 return {"ok": True}  # 200 = ack
                                         # Pub/Sub retries on non-2xx
```

- [ ] `analysis_agent/agent.py` — extract `analyze_finding()` as a pure function (takes finding_id, returns result), remove poll loop
- [ ] `scan_runner/runner.py` — extract `run_scan_pipeline()` as a pure function, remove poll loop
- [ ] `scan_runner/poller.py` — extract `run_sync_once()` as a pure function, remove `poll_loop()` and `asyncio.sleep()`
- [ ] The `--poll` CLI mode is no longer needed (Pub/Sub pushes work); keep `--finding-id` / `--scan-id` for manual runs

---

## PHASE 3 — API Service Migration

### 3.1 Update Dependencies
**File: `api_service/deps.py`**
- [ ] Replace `db_session()` → yield Firestore client from `get_firestore_client()`
- [ ] Remove `from shared.db import get_db` and `sqlalchemy` imports

### 3.2 Register Pub/Sub Handlers
**File: `api_service/main.py`**
- [ ] Add `app.include_router(tasks.router, prefix="/pubsub")` for Pub/Sub push subscription handlers
- [ ] Minor import updates

### 3.3 Migrate All Route Files
Each route file follows the same pattern: replace SQLAlchemy `select()`/`session.add()` with Firestore repository calls.

| Route File | Endpoints to Migrate |
|------------|---------------------|
| `repos.py` | `GET /api/repos`, `GET /api/repos/{id}` |
| `branches.py` | `GET /api/branches` |
| `artifacts.py` | `GET /api/artifacts` |
| `scans_manual.py` | `POST /api/scans/manual`, `GET` scans, rerun, sync (publish to Pub/Sub) |
| `findings.py` | `GET /api/findings`, `GET /api/findings/{id}`, analysis endpoints (publish to Pub/Sub) |
| `kb_under_findings.py` | KB fix card CRUD |
| `schedules.py` | Schedule CRUD (run-now publishes to Pub/Sub) |
| `audit.py` | Audit log listing |
| `webhooks.py` | Webhook handlers |
| `health.py` | Check Firestore connectivity instead of Postgres |

**For each file:**
- [ ] Remove `from sqlalchemy import select` and session usage
- [ ] Import and use the appropriate Firestore repository store
- [ ] Replace pagination (SQL `OFFSET/LIMIT`) with Firestore cursor-based pagination

---

## PHASE 4 — Scan Runner & Poller Migration

### 4.1 Migrate `scan_runner/orchestrator.py`
- [ ] Load scan + repo → `ScanStore.get_scan()`, `RepoStore.get_repo()`
- [ ] Store artifact → `ScanStore.add_artifact()`
- [ ] Store findings → `FindingStore.create_findings()` (Firestore batch write)
- [ ] Enqueue analysis → `pubsub_client.publish_message()` per finding
- [ ] Update build_id → `ScanStore.update_scan()`
- [ ] Remove all SQLAlchemy imports

### 4.2 Migrate `scan_runner/poller.py`
- [ ] `run_sync_once()` — replace all DB calls with Firestore repositories
- [ ] Remove `poll_loop()` and `asyncio.sleep()` — Cloud Scheduler triggers this
- [ ] Remove `main()` CLI entry — replaced by task handler endpoint
- [ ] Keep `run_sync_once()` as importable function for the task handler

### 4.3 Migrate `scan_runner/veracode_sync_api.py`
- [ ] `get_sync_state()` → Firestore single-doc read from `sync_state/veracode`
- [ ] `update_sync_state()` → Firestore single-doc update
- [ ] Remove `VeracodeSyncState` ORM model, SQLAlchemy imports

### 4.4 Migrate Normalization Files
- [ ] `scan_runner/normalize.py` — return Firestore-compatible dicts instead of ORM objects
- [ ] `scan_runner/normalize_xml_findings.py` — same change
- [ ] `scan_runner/veracode_xml_pipeline.py` — replace all DB operations with Firestore + Pub/Sub

### 4.5 Migrate `scan_runner/jobs.py`
- [ ] Replace `enqueue_job()` → `pubsub_client.publish_message()`
- [ ] Remove `claim_next_job()`, `complete_job()` (Pub/Sub handles delivery)
- [ ] Remove SQLAlchemy imports

### 4.6 Migrate `scan_runner/enqueue_analysis.py`
- [ ] Replace `enqueue_analysis_jobs()` — batch publish to `ccv-analyze-finding` Pub/Sub topic
- [ ] Remove `Job` model import

---

## PHASE 5 — Analysis Agent Migration

### 5.1 Migrate `analysis_agent/agent.py`
- [ ] Extract `analyze_finding(finding_id)` as a standalone async function:
  - Read finding from `FindingStore.get_finding()`
  - Run ADK agent
  - Store result via `AnalysisStore.create_analysis()`
- [ ] Remove `poll_jobs()` loop — replaced by `POST /pubsub/analyze-finding` push handler
- [ ] Keep `--finding-id` CLI for manual one-off analysis
- [ ] Remove all SQLAlchemy imports

### 5.2 Migrate `analysis_agent/tools.py`
- [ ] `lookup_kb_fix_card()` → use `KBFixCardStore.get_by_cwe()` from Firestore
- [ ] Remove SQLAlchemy session usage

### 5.3 Migrate `analysis_agent/jobs.py`
- [ ] Remove entirely — job delivery is handled by Pub/Sub push subscriptions

---

## PHASE 6 — KB Service Migration (RAG: pgvector → Vertex AI Vector Search)

### 6.1 Set Up Vertex AI Vector Search
- [ ] Create a Vector Search index (dimensions=3072, distance=COSINE_DISTANCE)
- [ ] Deploy index to an endpoint
- [ ] Plan update strategy: streaming updates (real-time) or batch updates

### 6.2 Migrate `kb_service/store.py`
- [ ] `get_fix_card(cwe_id)` → Firestore query on `kb_fix_cards` collection
- [ ] `get_fix_card_by_id(id)` → Firestore doc read
- [ ] `list_fix_cards(page, page_size)` → Firestore paginated query
- [ ] `upsert_fix_card()` → Firestore doc set + upsert datapoint to Vertex AI Vector Search index
- [ ] `update_fix_card()` → Firestore doc update
- [ ] `increment_usage()` → Firestore `Increment` field transform
- [ ] `vector_search(query_text)` → embed query → `MatchServiceClient.find_neighbors()` → fetch full docs from Firestore by ID
- [ ] Remove `create_pgvector_index()` — Vertex AI manages its own indexes
- [ ] Remove all SQLAlchemy, pgvector, and raw SQL imports

### 6.3 Migrate `kb_service/embeddings.py`
- [ ] Embedding generation stays the same (still uses `gemini-embedding-001`)
- [ ] Add helper to format embedding for Vertex AI Vector Search upsert

### 6.4 Migrate `kb_service/loader.py`
- [ ] CSV loader writes to Firestore (instead of SQLAlchemy)
- [ ] Also batch-upserts embeddings to Vertex AI Vector Search index
- [ ] Remove SQLAlchemy session usage

### 6.5 Migrate `kb_service/service.py`
- [ ] Update FastAPI endpoints to use Firestore-based store
- [ ] Remove pgvector references

---

## PHASE 7 — MCP Server & Shared Cleanup

### 7.1 Migrate `mcp_server/audit.py`
- [ ] Replace audit log writes with `AuditStore.log_entry()`
- [ ] Verify no SQLAlchemy imports remain

### 7.2 Update `mcp_server/main.py`
- [ ] Update health check to verify Firestore connectivity

### 7.3 Clean Up Shared Package
- [ ] **Delete** `shared/db.py`
- [ ] **Delete** `shared/models.py`
- [ ] Update `shared/__init__.py` exports
- [ ] Verify `shared/schemas.py` works unchanged (API schemas are ORM-independent)
- [ ] Clean `shared/utils.py` — remove any Postgres-specific helpers

### 7.4 Update All `pyproject.toml` Files
- [ ] `packages/shared/pyproject.toml` — remove Postgres deps, add Firestore + Pub/Sub
- [ ] `packages/api_service/pyproject.toml` — remove Alembic
- [ ] `packages/kb_service/pyproject.toml` — remove pgvector, add aiplatform
- [ ] Verify `analysis_agent` and `scan_runner` pyproject.toml have no direct Postgres deps

### 7.5 Update Infrastructure Files
- [ ] `docker-compose.yml` — remove Postgres service, add Firestore emulator (or document emulator startup separately)
- [ ] Delete `init-db.sql`
- [ ] `requirements.txt` — full dependency swap

---

## PHASE 8 — Data Migration (ETL: Postgres → Firestore + Vertex AI)

### 8.1 Build ETL Script
**File: `scripts/pg_to_firestore.py`** *(NEW)*
- [ ] Read all records from each Postgres table (temporary SQLAlchemy dependency)
- [ ] Transform to Firestore document format
- [ ] Batch-write to Firestore (500 docs per commit)
- [ ] Migrate embeddings from `kb_fix_cards.embedding` → Vertex AI Vector Search index
- [ ] Migrate `veracode_sync_state` → `sync_state/veracode` doc
- [ ] Discard old `jobs` rows (active jobs re-published to Pub/Sub topics)

### 8.2 Validate Migration
- [ ] Compare document counts per collection vs source table row counts
- [ ] Spot-check 10 random records per collection
- [ ] Run a sample vector search and compare results with pgvector
- [ ] Verify sync state preserved correctly

### 8.3 Handle In-Flight Work
- [ ] Drain running jobs before cutover (let them complete)
- [ ] Re-publish any QUEUED jobs to Pub/Sub topics

---

## PHASE 9 — Testing

### 9.1 Update Existing Tests
- [ ] `tests/test_api_health.py` — assert Firestore connectivity
- [ ] `tests/test_normalization.py` — use Firestore models instead of ORM
- [ ] `tests/test_mcp_call_contract.py` — verify no Postgres deps
- [ ] `tests/test_analysis_agent_contract.py` — mock Firestore + Pub/Sub instead of SQLAlchemy
- [ ] `tests/test_kb_vector_search.py` — test Vertex AI Vector Search (or mock)

### 9.2 Add New Tests
- [ ] Firestore CRUD tests per collection (using Firestore emulator)
- [ ] Pub/Sub publish test (mock `PublisherClient`, verify message published)
- [ ] Push subscription handler tests (`POST /pubsub/analyze-finding`, etc.)
- [ ] End-to-end: scan creation → findings stored → analysis message published → handler processes
- [ ] Vector search: embed query → find neighbors → fetch from Firestore

### 9.3 Test Configuration
- [ ] `conftest.py` — Firestore emulator fixture
- [ ] `conftest.py` — mock Pub/Sub publisher fixture (or use Pub/Sub emulator)
- [ ] Add `pyproject.toml` markers for integration vs unit tests

---

## PHASE 10 — Documentation Updates

### 10.1 Update `README.md`
- [ ] Replace architecture diagram (Firestore + Pub/Sub + Cloud Scheduler + Vertex AI)
- [ ] Update prerequisites (remove Docker/Postgres, add `gcloud` CLI + emulators)
- [ ] Update Quick Start: Firestore emulator + Pub/Sub emulator
- [ ] Remove Alembic migration step
- [ ] Update API endpoints table to include `/pubsub/*` push handlers

### 10.2 Update `RUN_COMMANDS.md`
- [ ] Remove Terminal 1 (Postgres Docker) → replace with Firestore emulator
- [ ] Remove Terminal 2 Alembic step
- [ ] Remove scan_runner `--poll` and analysis_agent `--poll` (no more polling)
- [ ] Add note: Cloud Scheduler triggers sync automatically
- [ ] Update Minimum Stack table

### 10.3 Update `DATA_MODEL.md`
- [ ] Replace SQL table definitions with Firestore collection schemas
- [ ] Replace ER diagram with collection/subcollection relationship diagram
- [ ] Document Pub/Sub topic + subscription schema
- [ ] Remove SQL indexes, constraints, enums

### 10.4 Update `.env.example`
- [ ] Already covered in Phase 0.4 — verify completeness

---

## PHASE 11 — Deployment & Cutover

### 11.1 Staging Deployment
- [ ] Deploy to Cloud Run / GCE / GKE with Firestore + Pub/Sub + Vertex AI
- [ ] Run ETL: production Postgres → staging Firestore
- [ ] Create Pub/Sub topics + push subscriptions pointing to deployed service
- [ ] Create Cloud Scheduler job for periodic Veracode sync
- [ ] Verify all API endpoints return correct data
- [ ] Verify UI pages render correctly
- [ ] Verify push handlers process Pub/Sub messages correctly
- [ ] Verify KB vector search works via Vertex AI

### 11.2 Production Cutover
- [ ] Freeze writes on production Postgres
- [ ] Run ETL on production data
- [ ] Validate document counts and data integrity
- [ ] Switch production config to Firestore + Pub/Sub
- [ ] Create production Cloud Scheduler jobs
- [ ] Deploy and monitor for 24h
- [ ] Keep Postgres read-only for 1 week as rollback safety net

### 11.3 Post-Migration Cleanup
- [ ] Remove ETL script's temporary SQLAlchemy dependency
- [ ] Remove any `DUAL_WRITE` feature flags
- [ ] Decommission Postgres instance
- [ ] Archive `Upgrade.md`

---

## PHASE 12 — Monitoring & Operations

### 12.1 Observability
- [ ] Instrument Firestore read/write latency and operation counts
- [ ] Monitor Pub/Sub subscription backlog, delivery rate, dead-letter count
- [ ] Monitor Vertex AI Vector Search query latency
- [ ] Set up Cloud Monitoring dashboards

### 12.2 Backup & Retention
- [ ] Firestore: schedule daily exports to GCS (`gcloud firestore export`)
- [ ] Define TTL for audit logs (e.g., auto-delete after 90 days)
- [ ] Vertex AI: index snapshots for rollback

### 12.3 Cost Management
- [ ] Set Firestore read/write budget alerts
- [ ] Monitor Pub/Sub billing (very cheap — ~$0.04/million messages)
- [ ] Cache frequently-read docs (repos, KB cards) in application memory
- [ ] Batch Firestore writes where possible (500 per commit)

---

## Files Impact Summary

### Files to DELETE (6)
| File | Reason |
|------|--------|
| `shared/db.py` | Replaced by `firestore_client.py` |
| `shared/models.py` | Replaced by `firestore_models.py` |
| `api_service/alembic/` (directory) | No SQL migrations |
| `api_service/alembic.ini` | No SQL migrations |
| `init-db.sql` | No SQL init |
| `analysis_agent/jobs.py` | Pub/Sub handles job delivery |

### Files to CREATE (15+)
| File | Purpose |
|------|---------|
| `shared/firestore_client.py` | Firestore async client singleton |
| `shared/firestore_models.py` | Pydantic document models |
| `shared/pubsub_client.py` | Pub/Sub publisher helper |
| `shared/repositories/base.py` | Abstract repository interfaces |
| `shared/repositories/repo_store.py` | Firestore repo CRUD |
| `shared/repositories/scan_store.py` | Firestore scan CRUD |
| `shared/repositories/finding_store.py` | Firestore finding CRUD |
| `shared/repositories/analysis_store.py` | Firestore analysis CRUD |
| `shared/repositories/schedule_store.py` | Firestore schedule CRUD |
| `shared/repositories/kb_store.py` | Firestore KB + Vertex AI search |
| `shared/repositories/audit_store.py` | Firestore audit log |
| `shared/repositories/user_store.py` | Firestore user CRUD |
| `shared/repositories/sync_state_store.py` | Firestore sync state |
| `api_service/routes/tasks.py` | Pub/Sub push subscription handlers |
| `scripts/pg_to_firestore.py` | One-time ETL migration |

### Files to MODIFY (35+)
| File | Change |
|------|--------|
| `shared/config.py` | Remove Postgres config, add Firestore/Pub/Sub/Vertex AI config |
| `shared/schemas.py` | Minimal — verify compatibility |
| `shared/__init__.py` | Update exports |
| `shared/utils.py` | Remove Postgres helpers |
| `api_service/deps.py` | Firestore dependency injection |
| `api_service/main.py` | Add pubsub handlers router |
| `api_service/routes/repos.py` | Firestore queries |
| `api_service/routes/branches.py` | Firestore queries |
| `api_service/routes/artifacts.py` | Firestore queries |
| `api_service/routes/scans_manual.py` | Firestore + Pub/Sub |
| `api_service/routes/findings.py` | Firestore + Pub/Sub |
| `api_service/routes/kb_under_findings.py` | Firestore queries |
| `api_service/routes/schedules.py` | Firestore + Pub/Sub |
| `api_service/routes/audit.py` | Firestore queries |
| `api_service/routes/webhooks.py` | Firestore queries |
| `api_service/routes/health.py` | Check Firestore |
| `scan_runner/orchestrator.py` | Firestore + Pub/Sub |
| `scan_runner/poller.py` | Firestore, remove poll loop |
| `scan_runner/runner.py` | Remove poll loop |
| `scan_runner/jobs.py` | Pub/Sub publish |
| `scan_runner/enqueue_analysis.py` | Pub/Sub publish |
| `scan_runner/normalize.py` | Firestore models |
| `scan_runner/normalize_xml_findings.py` | Firestore models |
| `scan_runner/veracode_xml_pipeline.py` | Firestore + Pub/Sub |
| `scan_runner/veracode_sync_api.py` | Firestore single-doc |
| `analysis_agent/agent.py` | Firestore + Pub/Sub handler, remove poll loop |
| `analysis_agent/tools.py` | Firestore KB lookup |
| `kb_service/store.py` | Firestore + Vertex AI Vector Search |
| `kb_service/loader.py` | Firestore + Vertex AI |
| `kb_service/service.py` | Firestore |
| `kb_service/embeddings.py` | Add Vertex AI Vector Search format |
| `mcp_server/audit.py` | Firestore audit log |
| `docker-compose.yml` | Remove Postgres |
| `requirements.txt` | Dependency swap |
| `.env.example` | Config vars |
| All 5 test files | Firestore + Pub/Sub mocks |
| `README.md` | Full rewrite of setup sections |
| `RUN_COMMANDS.md` | Update all terminals |
| `DATA_MODEL.md` | Firestore schema |
| `packages/shared/pyproject.toml` | Dependency swap (Firestore + Pub/Sub) |
| `packages/kb_service/pyproject.toml` | Remove pgvector |
