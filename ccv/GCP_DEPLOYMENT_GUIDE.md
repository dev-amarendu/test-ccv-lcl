# CCV — Complete GCP Deployment Guide

This guide walks through deploying the **entire** CCV solution to Google Cloud Platform using a dedicated **Service Account** for authentication across all services.

---

## Solution Component Map

| # | Component | Runtime | GCP Service | Port |
|---|-----------|---------|-------------|------|
| 1 | **web_ui** | React SPA (Vite) | Firebase Hosting | — |
| 2 | **api_service** | FastAPI (Python) | Cloud Run | 8080 |
| 3 | **mcp_server** | FastAPI (Python) | Cloud Run | 8080 |
| 4 | **kb_service** | FastAPI (Python) | Cloud Run | 8080 |
| 5 | **scan_runner** | Pub/Sub → api_service | *(handled by #2)* | — |
| 6 | **analysis_agent** | Pub/Sub → api_service | *(handled by #2)* | — |
| 7 | **poller** | Cloud Scheduler → api_service | *(handled by #2)* | — |

> [!NOTE]
> Components 5, 6, 7 are **not separate deployments**. They are triggered via Pub/Sub Push subscriptions that POST to the `api_service` Cloud Run instance at `/pubsub/run-scan`, `/pubsub/analyze-finding`, and `/pubsub/sync-veracode` respectively. Cloud Scheduler triggers the poller periodically.

---

## Prerequisites

```bash
# Install CLIs
# gcloud: https://cloud.google.com/sdk/docs/install
# firebase: npm install -g firebase-tools

# Set your project
export PROJECT_ID="<YOUR_GCP_PROJECT_ID>"
export REGION="us-central1"
```

---

## Step 1: Enable Required APIs

```bash
gcloud config set project $PROJECT_ID

gcloud services enable \
  run.googleapis.com \
  artifactregistry.googleapis.com \
  firestore.googleapis.com \
  pubsub.googleapis.com \
  secretmanager.googleapis.com \
  aiplatform.googleapis.com \
  cloudscheduler.googleapis.com \
  cloudbuild.googleapis.com
```

---

## Step 2: Create a Dedicated Service Account

Create a single service account that all 3 Cloud Run services will use. This account needs access to Firestore, Pub/Sub, Vertex AI, and Secret Manager.

```bash
# Create the service account
gcloud iam service-accounts create ccv-runtime \
  --display-name="CCV Runtime Service Account"

export SA_EMAIL="ccv-runtime@${PROJECT_ID}.iam.gserviceaccount.com"

# Grant IAM roles
gcloud projects add-iam-policy-binding $PROJECT_ID \
  --member="serviceAccount:${SA_EMAIL}" \
  --role="roles/datastore.user"

gcloud projects add-iam-policy-binding $PROJECT_ID \
  --member="serviceAccount:${SA_EMAIL}" \
  --role="roles/pubsub.publisher"

gcloud projects add-iam-policy-binding $PROJECT_ID \
  --member="serviceAccount:${SA_EMAIL}" \
  --role="roles/pubsub.subscriber"

gcloud projects add-iam-policy-binding $PROJECT_ID \
  --member="serviceAccount:${SA_EMAIL}" \
  --role="roles/secretmanager.secretAccessor"

gcloud projects add-iam-policy-binding $PROJECT_ID \
  --member="serviceAccount:${SA_EMAIL}" \
  --role="roles/aiplatform.user"

gcloud projects add-iam-policy-binding $PROJECT_ID \
  --member="serviceAccount:${SA_EMAIL}" \
  --role="roles/storage.objectAdmin"

gcloud projects add-iam-policy-binding $PROJECT_ID \
  --member="serviceAccount:${SA_EMAIL}" \
  --role="roles/run.invoker"
```

---

## Step 3: Store Secrets in Secret Manager

```bash
# Veracode credentials
echo -n "<YOUR_VERACODE_API_ID>" | \
  gcloud secrets create VERACODE_API_KEY_ID --data-file=- --replication-policy=automatic

echo -n "<YOUR_VERACODE_API_SECRET>" | \
  gcloud secrets create VERACODE_API_KEY_SECRET --data-file=- --replication-policy=automatic

# Bitbucket token (if applicable)
echo -n "<YOUR_BITBUCKET_TOKEN>" | \
  gcloud secrets create BITBUCKET_TOKEN --data-file=- --replication-policy=automatic

# MCP internal auth token
echo -n "<GENERATE_A_RANDOM_TOKEN>" | \
  gcloud secrets create MCP_INTERNAL_TOKEN --data-file=- --replication-policy=automatic
```

---

## Step 4: Create Artifact Registry

```bash
gcloud artifacts repositories create ccv-images \
  --repository-format=docker \
  --location=$REGION \
  --description="CCV Docker images"

gcloud auth configure-docker ${REGION}-docker.pkg.dev
```

---

## Step 5: Create Firestore Database

```bash
gcloud firestore databases create --location=$REGION
```

---

## Step 6: Deploy Cloud Run Services

### 6a. Deploy `api-service` (main backend + background workers)

This is the core service. It handles all REST API requests from the frontend AND all Pub/Sub push messages for scan_runner, analysis_agent, and poller.

```bash
gcloud run deploy api-service \
  --source . \
  --region=$REGION \
  --service-account=$SA_EMAIL \
  --allow-unauthenticated \
  --memory=2Gi \
  --timeout=3600 \
  --set-env-vars="\
GOOGLE_CLOUD_PROJECT=${PROJECT_ID},\
FIRESTORE_PROJECT_ID=${PROJECT_ID},\
GOOGLE_CLOUD_LOCATION=${REGION},\
GOOGLE_GENAI_USE_VERTEXAI=true,\
PUBSUB_PROJECT_ID=${PROJECT_ID}" \
  --set-secrets="\
VERACODE_API_KEY_ID=VERACODE_API_KEY_ID:latest,\
VERACODE_API_KEY_SECRET=VERACODE_API_KEY_SECRET:latest,\
MCP_INTERNAL_TOKEN=MCP_INTERNAL_TOKEN:latest"
```

> [!IMPORTANT]
> Note the **Service URL** printed after deployment (e.g. `https://api-service-abc123-uc.a.run.app`). You'll need it for Pub/Sub, Scheduler, and the frontend.

```bash
export API_URL="<paste-the-url-here>"
```

### 6b. Deploy `mcp-server`

The MCP Server needs its own Dockerfile entry point. Create `Dockerfile.mcp`:

```dockerfile
FROM python:3.11-slim
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1
RUN apt-get update && apt-get install -y --no-install-recommends curl build-essential && rm -rf /var/lib/apt/lists/*
RUN pip install poetry
WORKDIR /app
COPY pyproject.toml poetry.lock ./
COPY packages/ ./packages/
RUN poetry config virtualenvs.create false && poetry install --no-interaction --no-root --only main
COPY . .
RUN poetry install --no-interaction --only main
ENV PYTHONPATH="/app/packages/shared:/app/packages/mcp_server"
EXPOSE 8080
CMD ["uvicorn", "mcp_server.main:app", "--host", "0.0.0.0", "--port", "8080", "--proxy-headers"]
```

```bash
gcloud run deploy mcp-server \
  --source . \
  --dockerfile=Dockerfile.mcp \
  --region=$REGION \
  --service-account=$SA_EMAIL \
  --no-allow-unauthenticated \
  --set-env-vars="\
GOOGLE_CLOUD_PROJECT=${PROJECT_ID},\
FIRESTORE_PROJECT_ID=${PROJECT_ID}" \
  --set-secrets="MCP_INTERNAL_TOKEN=MCP_INTERNAL_TOKEN:latest"
```

```bash
export MCP_URL="<paste-mcp-service-url>"
```

Then update api-service to point to the MCP server:
```bash
gcloud run services update api-service \
  --region=$REGION \
  --update-env-vars="MCP_BASE_URL=${MCP_URL}"
```

### 6c. Deploy `kb-service`

Create `Dockerfile.kb`:

```dockerfile
FROM python:3.11-slim
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1
RUN apt-get update && apt-get install -y --no-install-recommends curl build-essential && rm -rf /var/lib/apt/lists/*
RUN pip install poetry
WORKDIR /app
COPY pyproject.toml poetry.lock ./
COPY packages/ ./packages/
RUN poetry config virtualenvs.create false && poetry install --no-interaction --no-root --only main
COPY . .
RUN poetry install --no-interaction --only main
ENV PYTHONPATH="/app/packages/shared:/app/packages/kb_service"
EXPOSE 8080
CMD ["uvicorn", "kb_service.service:app", "--host", "0.0.0.0", "--port", "8080", "--proxy-headers"]
```

```bash
gcloud run deploy kb-service \
  --source . \
  --dockerfile=Dockerfile.kb \
  --region=$REGION \
  --service-account=$SA_EMAIL \
  --no-allow-unauthenticated \
  --set-env-vars="\
GOOGLE_CLOUD_PROJECT=${PROJECT_ID},\
FIRESTORE_PROJECT_ID=${PROJECT_ID},\
GOOGLE_CLOUD_LOCATION=${REGION}"
```

---

## Step 7: Create Pub/Sub Topics & Push Subscriptions

These connect the event-driven background workers (scan_runner, analysis_agent) to the api-service Cloud Run instance.

```bash
# Topic 1: Run Scan (triggers scan_runner via api-service)
gcloud pubsub topics create ccv-run-scan
gcloud pubsub subscriptions create ccv-run-scan-push \
  --topic=ccv-run-scan \
  --push-endpoint="${API_URL}/pubsub/run-scan" \
  --ack-deadline=600 \
  --push-auth-service-account=$SA_EMAIL

# Topic 2: Analyze Finding (triggers analysis_agent via api-service)
gcloud pubsub topics create ccv-analyze-finding
gcloud pubsub subscriptions create ccv-analyze-finding-push \
  --topic=ccv-analyze-finding \
  --push-endpoint="${API_URL}/pubsub/analyze-finding" \
  --ack-deadline=120 \
  --push-auth-service-account=$SA_EMAIL

# Topic 3: Sync Veracode (triggers poller via api-service)
gcloud pubsub topics create ccv-sync-veracode
gcloud pubsub subscriptions create ccv-sync-veracode-push \
  --topic=ccv-sync-veracode \
  --push-endpoint="${API_URL}/pubsub/sync-veracode" \
  --ack-deadline=300 \
  --push-auth-service-account=$SA_EMAIL

# Topic 4: Embed KB Card (triggers embedding generation)
gcloud pubsub topics create ccv-embed-kb
gcloud pubsub subscriptions create ccv-embed-kb-push \
  --topic=ccv-embed-kb \
  --push-endpoint="${API_URL}/pubsub/embed-kb" \
  --ack-deadline=60 \
  --push-auth-service-account=$SA_EMAIL
```

---

## Step 8: Create Cloud Scheduler for Veracode Poller

This replaces the local `poller.py` loop. Cloud Scheduler will publish a message to `ccv-sync-veracode` every 5 minutes, which triggers the push subscription endpoint.

```bash
gcloud scheduler jobs create pubsub veracode-sync-job \
  --schedule="*/5 * * * *" \
  --topic=ccv-sync-veracode \
  --message-body='{"action": "sync"}' \
  --location=$REGION \
  --time-zone="UTC"
```

---

## Step 9: Deploy the Frontend (Firebase Hosting)

```bash
cd packages/web_ui

# Point the frontend at the prod API
echo "VITE_API_URL=${API_URL}" > .env.production

# Build the optimized bundle
npm run build

# Initialize and deploy Firebase Hosting
firebase login
firebase use --add $PROJECT_ID
firebase deploy --only hosting
```

The `firebase.json` already exists with SPA rewrite rules and caching headers.

---

## Architecture Diagram

```
┌─────────────────────┐
│   Firebase Hosting   │ ◀── Static React SPA
│   (CDN / HTTPS)      │
└────────┬────────────┘
         │ HTTPS /api/*
         ▼
┌─────────────────────┐     ┌──────────────────┐
│   Cloud Run          │────▶│  Firestore        │
│   api-service        │     │  (NoSQL DB)       │
│   ├─ REST API        │     └──────────────────┘
│   ├─ /pubsub/run-scan│
│   ├─ /pubsub/analyze │     ┌──────────────────┐
│   └─ /pubsub/sync    │────▶│  Secret Manager   │
└────────┬────────────┘     └──────────────────┘
         │
    ┌────┴────┐
    ▼         ▼
┌────────┐ ┌────────┐     ┌──────────────────┐
│Pub/Sub │ │Cloud   │     │  Cloud Run        │
│Topics  │ │Sched.  │     │  mcp-server       │
│(push)  │ │(cron)  │     └──────────────────┘
└────────┘ └────────┘     ┌──────────────────┐
                          │  Cloud Run        │
                          │  kb-service       │
    Service Account:      └──────────────────┘
    ccv-runtime@...
    ├─ datastore.user
    ├─ pubsub.publisher
    ├─ pubsub.subscriber
    ├─ secretmanager.secretAccessor
    ├─ aiplatform.user
    ├─ storage.objectAdmin
    └─ run.invoker
```

---

## Verification Checklist

After deployment, verify each component:

| Check | Command |
|-------|---------|
| API health | `curl ${API_URL}/health` |
| MCP health | `curl -H "Authorization: Bearer <token>" ${MCP_URL}/health` |
| KB health | `curl ${KB_URL}/health` |
| Frontend loads | Open Firebase Hosting URL in browser |
| Pub/Sub scan | Trigger a manual scan from the UI → check Cloud Run logs |
| Scheduler runs | `gcloud scheduler jobs describe veracode-sync-job --location=$REGION` |
| Firestore data | Check Firebase Console → Firestore for `scans` collection |
