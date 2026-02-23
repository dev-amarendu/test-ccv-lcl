# CCV — Cox Code Vulnerability (GCP Native)

CCV is a serverless, event-driven security platform that ingests Veracode SAST results, normalizes findings into Firestore, and enriches them with AI-powered remediation guidance using Google Vertex AI (Gemini).

The architecture is fully cloud-native, leveraging **Google Cloud Firestore**, **Cloud Pub/Sub**, **Cloud Scheduler**, and **Vertex AI Vector Search**.

---

## Architecture (Serverless)

```mermaid
graph TD
    User[React UI] -->|HTTP| API[API Service (Cloud Run)]
    API -->|Read/Write| DB[(Firestore)]
    
    Veracode[Veracode Platform] -->|Poll| Poller[Scan Poller (Cloud Run Job)]
    Poller -->|Write| DB
    Poller -->|Publish| PS[Pub/Sub Topic: new-finding]
    
    PS -->|Push| API
    API -->|Invoke| Agent[Analysis Agent Logic]
    Agent -->|RAG Lookup| KB[KB Service + Vertex AI]
    Agent -->|Write Analysis| DB
    
    MCP[MCP Server] -->|Tool Use| DB
    
    Scheduler[Cloud Scheduler] -->|Trigger| Poller
```

---

## Key Features

- **Centralized Vulnerability Data**: Single pane of glass for Veracode SAST findings.
- **AI-Driven Analysis**: Automatic root cause analysis and fix guidance using Gemini 1.5 Pro.
- **RAG Remediation**: Retrieves validated fix patterns ("Fix Cards") from Vertex AI Vector Search.
- **Event-Driven Workflow**: Pub/Sub triggers analysis immediately upon finding ingestion.
- **Serverless**: No managing Postgres servers, Redis queues, or polling loops.
- **MCP Integration**: Exposes data and tools to LLM-based IDE assistants (Cursor, Windsurf).

---

## Tech Stack

- **Backend**: Python 3.11, FastAPI
- **Database**: Google Cloud Firestore (NoSQL)
- **Queue**: Google Cloud Pub/Sub
- **AI/ML**: Google Vertex AI (Gemini + Vector Search)
- **Frontend**: React, Vite, TypeScript, Tailwind
- **Infrastructure**: Docker for local dev; Cloud Run for production

---

## Prerequisites

- Python 3.11+
- Node.js 20+
- Google Cloud Project with:
  - Firestore (Native mode)
  - Pub/Sub API enabled
  - Vertex AI API enabled
- `gcloud` CLI installed and authenticated

---

## Quick Start

### 1. Configure Environment

```bash
cp .env.example .env
# Set GOOGLE_CLOUD_PROJECT, FIRESTORE_PROJECT_ID, VERACODE_API_KEY_ID, etc.
```

### 2. Authenticate with GCP

```bash
gcloud auth application-default login
export GOOGLE_CLOUD_PROJECT=your-project-id
```

### 3. Install Dependencies

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 4. Run Services

See [RUN_COMMANDS.md](./RUN_COMMANDS.md) for detailed instructions on running each component locally.

- **API Service**: `python -m api_service.main`
- **MCP Server**: `python -m mcp_server.main`
- **Frontend**: `npm run dev` (in `packages/web_ui`)

---

## API Endpoints

| Service | Port | Description |
|---|---|---|
| **API** | 8008 | Main REST API (`/api/findings`, `/api/scans`) |
| **MCP** | 8001 | Model Context Protocol server for IDEs |
| **KB** | 8002 | Knowledge Base service (embeddings) |
| **UI** | 5173 | React Frontend |

---

## Data Model

Data is stored in **Firestore** collections:
- `repos`, `scans`, `findings`, `finding_analyses`
- `kb_fix_cards` (Uses Vertex AI for vector search)
- `audit_logs`, `schedules`

See [DATA_MODEL.md](./DATA_MODEL.md) for the full schema.

---

## Project Structure

```
ccv/
├── packages/
│   ├── shared/              # Config, Firestore models, Pub/Sub client
│   ├── api_service/         # FastAPI, Pub/Sub handlers (Push)
│   ├── mcp_server/          # MCP tools
│   ├── scan_runner/         # Poller logic, Veracode client
│   ├── analysis_agent/      # Gemini prompting logic
│   ├── kb_service/          # Vertex AI Vector Search logic
│   └── web_ui/              # React Frontend
├── scripts/                 # ETL and utility scripts
└── tests/                   # Pytest suite
```

---

## Code Ownership

| Area | Owner |
|---|---|
| Core Platform (API, DB, Poller) | Dev1 |
| AI Analysis (Prompts, Agent) | Dev2 |
| RAG / Knowledge Base | Dev3 |
| Frontend UX | Dev4 |
