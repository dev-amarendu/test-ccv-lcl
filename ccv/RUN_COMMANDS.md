# CCV — Run Commands (GCP Native)

All commands to run the full CCV stack locally. Each section represents a separate terminal.

---

## 1. Prerequisites (GCP Setup)

Before you begin, ensure you have:
1.  **Google Cloud Project**: Created with billing enabled.
2.  **APIs Enabled**:
    *   Firestore (Native Mode)
    *   Cloud Pub/Sub
    *   Vertex AI API
3.  **Service Account (Optional)**: Or personal account with `Editor` or `Owner` role.

---

## 2. Authentication

Authenticate your local machine so the diverse services (API, Poller, Agent) can access your GCP resources directly.

```bash
# Authenticate with your Google account (ADC)
gcloud auth application-default login

# Set the active project context
gcloud config set project YOUR_PROJECT_ID
```

---

## 3. Environment Configuration

Create your `.env` file in the root `ccv/` directory and ensure these variables are set.

```bash
cd ~/Desktop/ccv-opus/ccv
cp .env.example .env
```

**Required `.env` variables:**
```ini
# Google Cloud
GOOGLE_CLOUD_PROJECT=your-project-id
FIRESTORE_PROJECT_ID=your-project-id
PUBSUB_PROJECT_ID=your-project-id
GOOGLE_CLOUD_LOCATION=us-central1
GOOGLE_GENAI_USE_VERTEXAI=true

# Veracode Credentials (for fetching findings)
VERACODE_API_KEY_ID=your-api-id
VERACODE_API_KEY_SECRET=your-api-secret

# Optional: Service Account JSON path (if not using ADC)
# GOOGLE_APPLICATION_CREDENTIALS=/path/to/sa.json
```

---

## 4. Install Dependencies

**Backend (Python):**

```bash
cd ~/Desktop/ccv-opus/ccv
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

**Frontend (Node.js):**

```bash
cd ~/Desktop/ccv-opus/ccv/packages/web_ui
npm install
```

---

## 5. Run Services (5 Terminals)

You will need **5 separate terminal windows** to run the full stack locally.

### Terminal 1: API Service (Port 8008)

The core backend REST API.

```bash
cd ~/Desktop/ccv-opus/ccv
source .venv/bin/activate
python3 -m api_service.main
# API docs at http://localhost:8008/docs
```

### Terminal 2: MCP Server (Port 8001)

Model Context Protocol server for IDE integration (Cursor, Windsurf).

```bash
cd ~/Desktop/ccv-opus/ccv
source .venv/bin/activate
python3 -m mcp_server.main
# MCP at http://localhost:8001
```

### Terminal 3: Scan Poller (Background Worker)

Runs periodically to fetch new scans from Veracode.

```bash
cd ~/Desktop/ccv-opus/ccv
source .venv/bin/activate
# Polls Veracode every 5 mins (default)
python3 -m scan_runner.poller
```

> **Note:** The Analysis Agent logic is now event-driven via Pub/Sub and handled by the API Service or Cloud Run. You do not need a separate terminal for the agent unless debugging specific worker logic.

### Terminal 4: KB Service (Port 8002)

Knowledge Base service for RAG (Vertex AI Vector Search).

```bash
cd ~/Desktop/ccv-opus/ccv
source .venv/bin/activate
python3 -m kb_service.service
# KB API at http://localhost:8002
```

### Terminal 5: React UI (Port 5173)

The frontend web application.

```bash
cd ~/Desktop/ccv-opus/ccv/packages/web_ui
VITE_ENV=LOCAL npm run dev
# UI at http://localhost:5173
```

---

## 6. Utilities & One-off Tasks

### Data Migration (Postgres -> Firestore)

If you have data in the old PostgreSQL database that you want to move to Firestore. Requires both PG credentials in `.env` AND valid GCP Auth.

```bash
python3 scripts/pg_to_firestore.py
```

### Load KB Fix Cards

Load CWE remediation guidance into Vertex AI Vector Search.

```bash
python3 -m kb_service.loader --csv-path /path/to/cwe-660.csv
```

### Run Tests

Verify everything is working correctly.

```bash
pytest tests/ -v
```
