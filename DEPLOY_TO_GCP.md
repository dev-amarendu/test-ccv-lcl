# CCV — Deploy to GCP (step-by-step)

This document collects the full, actionable steps to deploy the CCV project (working tree: `test-ccv-lcl/ccv`) to Google Cloud Platform (GCP), including local emulator tips, infra requirements, build & deploy commands, and verification steps.

Use this as a checklist and copy/paste runnable commands (replace variables like `GCP_PROJECT`, `BUCKET`, and region as needed).

---

## 0. Quick variables (set these for your environment)

```bash
# Replace values for your environment
export GCP_PROJECT="my-ccv-project"
export REGION="us-central1"
export BUCKET="ccv-raw-${GCP_PROJECT}"
export SA_NAME="ccv-runner"
```

---

## 1. Prerequisites
- Install gcloud SDK, Docker, and optionally Cloud Build tools.
- Authenticate gcloud (preferred: service account for CI; local dev may use ADC):
  - Interactive ADC (dev):
    `gcloud auth application-default login --no-launch-browser`
  - Service account (recommended for CI):
    Create SA and download key, then:
    `export GOOGLE_APPLICATION_CREDENTIALS="/path/to/key.json"`
    `gcloud config set project $GCP_PROJECT`
- Ensure billing enabled for the project.

---

## 2. Enable required GCP APIs

```bash
gcloud services enable \
  firestore.googleapis.com \
  pubsub.googleapis.com \
  run.googleapis.com \
  cloudbuild.googleapis.com \
  cloudscheduler.googleapis.com \
  storage.googleapis.com \
  aiplatform.googleapis.com \
  monitoring.googleapis.com \
  logging.googleapis.com
```

---

## 3. Create a service account & grant roles

Create SA and bind initial roles (tweak for least privilege later):

```bash
gcloud iam service-accounts create $SA_NAME --display-name="CCV runner"
SA_EMAIL="${SA_NAME}@${GCP_PROJECT}.iam.gserviceaccount.com"

# Example roles (adjust to principle of least privilege later)
gcloud projects add-iam-policy-binding $GCP_PROJECT --member="serviceAccount:${SA_EMAIL}" --role="roles/datastore.user"
gcloud projects add-iam-policy-binding $GCP_PROJECT --member="serviceAccount:${SA_EMAIL}" --role="roles/pubsub.publisher"
gcloud projects add-iam-policy-binding $GCP_PROJECT --member="serviceAccount:${SA_EMAIL}" --role="roles/pubsub.subscriber"
gcloud projects add-iam-policy-binding $GCP_PROJECT --member="serviceAccount:${SA_EMAIL}" --role="roles/storage.admin"
gcloud projects add-iam-policy-binding $GCP_PROJECT --member="serviceAccount:${SA_EMAIL}" --role="roles/aiplatform.user"
gcloud projects add-iam-policy-binding $GCP_PROJECT --member="serviceAccount:${SA_EMAIL}" --role="roles/logging.logWriter"
gcloud projects add-iam-policy-binding $GCP_PROJECT --member="serviceAccount:${SA_EMAIL}" --role="roles/monitoring.metricWriter"
```

Create and download a key for CI (optional):

```bash
gcloud iam service-accounts keys create ~/ccv-sa.json --iam-account="$SA_EMAIL"
export GOOGLE_APPLICATION_CREDENTIALS=~/ccv-sa.json
```

---

## 4. Create GCS bucket for raw SCA and artifacts

```bash
gsutil mb -p $GCP_PROJECT -l $REGION gs://$BUCKET
```

Set bucket IAM or fine-grained permissions later; the SA needs upload/read rights.

---

## 5. Create Pub/Sub topics

```bash
gcloud pubsub topics create ccv-analyze-finding
gcloud pubsub topics create ccv-run-scan
gcloud pubsub topics create ccv-sync-veracode
gcloud pubsub topics create ccv-embed-kb
gcloud pubsub topics create ccv-normalize-report
```

---

## 6. Create Firestore database

Use the console to create Firestore (Native mode) in your target region. Note the project and database name (default is `(default)`).

> Firestore creation is usually a one-time manual step in the Cloud Console.

---

## 7. Create Vertex AI Vector Search index

Via Console → Vertex AI → Vector Search:
- Create an index with `dimensions = 3072` (or `settings.embed_dim`), distance = COSINE.
- Deploy the index to an endpoint and note `INDEX_ID` and `ENDPOINT_ID`.

Set those values in env config for services that will upsert/search vectors.

---

## 8. Build & push container images (Cloud Build)

Example build/push sequence (adjust service names and package paths):

```bash
# From repo root (test-ccv-lcl)
gcloud builds submit --tag gcr.io/$GCP_PROJECT/ccv-api test-ccv-lcl/ccv/packages/api_service
gcloud builds submit --tag gcr.io/$GCP_PROJECT/ccv-mcp test-ccv-lcl/ccv/packages/mcp_server
gcloud builds submit --tag gcr.io/$GCP_PROJECT/ccv-scan-runner test-ccv-lcl/ccv/packages/scan_runner
gcloud builds submit --tag gcr.io/$GCP_PROJECT/ccv-analysis-agent test-ccv-lcl/ccv/packages/analysis_agent
gcloud builds submit --tag gcr.io/$GCP_PROJECT/ccv-kb test-ccv-lcl/ccv/packages/kb_service
```

Each package should include a Dockerfile or you can add one (see examples below).

---

## 9. Deploy to Cloud Run

Example: deploy API service

```bash
gcloud run deploy ccv-api \
  --image gcr.io/$GCP_PROJECT/ccv-api \
  --platform managed \
  --region $REGION \
  --allow-unauthenticated \
  --service-account="$SA_EMAIL" \
  --set-env-vars="FIRESTORE_PROJECT_ID=$GCP_PROJECT,FIRESTORE_DATABASE=(default),PUBSUB_PROJECT_ID=$GCP_PROJECT,GCS_BUCKET=$BUCKET,GOOGLE_CLOUD_PROJECT=$GCP_PROJECT"
```

Repeat for other services (mcp, scan-runner, analysis-agent, kb) and set appropriate env vars (PUBSUB topic names, Vertex index ids, VERACODE credentials).

Notes:
- Prefer `--no-allow-unauthenticated` for internal services and use IAM to grant invoker role to Pub/Sub push service account or Cloud Scheduler.
- For Pub/Sub push to a Cloud Run endpoint, configure push subscription to use OIDC token with service account (recommended).

---

## 10. Create Pub/Sub push subscriptions (Cloud Run endpoints)

Example push subscription (use your Cloud Run service URL and OIDC auth):

```bash
API_URL="https://<ccv-api-url>"  # Cloud Run URL for api service
gcloud pubsub subscriptions create normalize-report-sub \
  --topic=ccv-normalize-report \
  --push-endpoint="${API_URL}/pubsub/normalize-report" \
  --ack-deadline=60 \
  --push-auth-service-account="$SA_EMAIL"
```

Create subscriptions for other topics similarly (ccv-analyze-finding, etc.) or run workers that pull from subscriptions.

---

## 11. Secrets & configuration

- Store sensitive values in Secret Manager (VERACODE_API_KEY_ID, VERACODE_API_KEY_SECRET, etc).
- In Cloud Run, configure env vars and mount secrets or use the Secret Manager integration.
- At minimum set env vars:
  - FIRESTORE_PROJECT_ID, FIRESTORE_DATABASE
  - PUBSUB_PROJECT_ID, PUBSUB_TOPIC_ANALYZE_FINDING, PUBSUB_TOPIC_RUN_SCAN, PUBSUB_TOPIC_SYNC_VERACODE, PUBSUB_TOPIC_EMBED_KB
  - GCS_BUCKET
  - VECTOR_SEARCH_INDEX_ID, VECTOR_SEARCH_INDEX_ENDPOINT
  - GOOGLE_CLOUD_PROJECT

---

## 12. (Optional) Run setup script to create collection markers

If ADC or emulator available run:

```bash
python3 test-ccv-lcl/ccv/scripts/setup_firestore_schema.py
```

If using emulator set:

```bash
export FIRESTORE_EMULATOR_HOST=localhost:8080
export GOOGLE_CLOUD_PROJECT=local-project
```

---

## 13. Migrate legacy data (Postgres → Firestore)

If you have Postgres data to migrate use:

```bash
python3 test-ccv-lcl/ccv/scripts/pg_to_firestore.py
```

This script expects Postgres credentials in env vars (see its header) and will batch-write into Firestore and GCS as configured.

---

## 14. Trigger & verify end-to-end flow

1. Trigger manual scan via API:

```bash
curl -X POST -H "Content-Type: application/json" \
  -d '{"repo_id":"<repo_id>","branch":"main"}' \
  https://<ccv-api-url>/api/scans/manual
```

2. Verify Firestore:
  - `scans` collection should have a new ScanDoc.
  - `findings` should be created after normalization / runner completion.
  - `finding_analyses` created by analysis agent.

3. Check Pub/Sub metrics and Cloud Run logs for errors.

---

## 15. Cloud Scheduler (periodic sync)

```bash
gcloud scheduler jobs create pubsub veracode-sync-job \
  --schedule="*/5 * * * *" \
  --topic=ccv-sync-veracode \
  --message-body='{}' \
  --location=$REGION
```

---

## 16. Monitoring & alerts

- Use Cloud Monitoring dashboards to monitor:
  - Firestore read/write latency and ops
  - Pub/Sub backlog and delivery rate
  - Cloud Run CPU/memory and request latencies
  - Vertex AI query latency and errors
- Create alerts for high Pub/Sub backlogs or Firestore errors.

---

## 17. Local development with emulators

Start Firestore emulator:
```bash
gcloud beta emulators firestore start --host-port=localhost:8080
export FIRESTORE_EMULATOR_HOST=localhost:8080
export GOOGLE_CLOUD_PROJECT=local-project
```

Start Pub/Sub emulator:
```bash
gcloud beta emulators pubsub start --host-port=8085
export PUBSUB_EMULATOR_HOST=localhost:8085
```

Run services locally using `.venv` and run FastAPI/uvicorn or debug in your IDE.

---

## 18. Troubleshooting tips
- Firestore auth errors: ensure `GOOGLE_APPLICATION_CREDENTIALS` or ADC is set, or use emulator.
- Pub/Sub push failures: ensure push endpoint URL is correct and push subscription has OIDC auth configured.
- Vertex issues: confirm index dimension equals embedding vector length.
- Cloud Run 403: grant Cloud Run Invoker role to the Pub/Sub push service account or allow unauthenticated for testing.

---

## 19. Next steps you may want me to implement
- (A) Add Dockerfiles and Cloud Build config for each package.
- (B) Implement normalization worker and Cloud Run job definition (container + sample).
- (C) Generate `.env.deploy` example with all env vars and Secret Manager instructions.

Pick an item above and I will implement it inside `test-ccv-lcl/`.

**************************************************************
****************************************************************************************************************************

Good — here’s a clear, actionable step‑by‑step guide to deploy the CCV project (now working in test-ccv-lcl/ccv) to GCP and run it. I include prerequisites, infra resources, build + deploy steps, config, and verification / run steps. Use this as your checklist.
1) Prerequisites (local)
gcloud SDK installed and authenticated (or have a service-account key).
Docker installed (for building container images).
Project id: pick GCP_PROJECT (e.g. my-ccv-project).
Billing enabled for the project.
From repo root ensure you are in test-ccv-lcl/ccv.
2) Create a GCP project (if you don’t have one)
gcloud projects create my-ccv-project --name="ccv"
gcloud config set project my-ccv-project
Enable billing for project.
3) Enable required GCP APIs
gcloud services enable \
firestore.googleapis.com \
pubsub.googleapis.com \
run.googleapis.com \
cloudbuild.googleapis.com \
cloudscheduler.googleapis.com \
storage.googleapis.com \
aiplatform.googleapis.com \
monitoring.googleapis.com \
logging.googleapis.com
4) Create a service account for the app (recommended)
Create SA:
gcloud iam service-accounts create ccv-runner --display-name="ccv-runner"
Grant roles (adjust least-privilege later):
gcloud projects add-iam-policy-binding $GCP_PROJECT --member="serviceAccount:ccv-runner@$GCP_PROJECT.iam.gserviceaccount.com" --role="roles/datastore.user"
gcloud projects add-iam-policy-binding $GCP_PROJECT --member="serviceAccount:ccv-runner@$GCP_PROJECT.iam.gserviceaccount.com" --role="roles/pubsub.publisher"
gcloud projects add-iam-policy-binding $GCP_PROJECT --member="serviceAccount:ccv-runner@$GCP_PROJECT.iam.gserviceaccount.com" --role="roles/pubsub.subscriber"
gcloud projects add-iam-policy-binding $GCP_PROJECT --member="serviceAccount:ccv-runner@$GCP_PROJECT.iam.gserviceaccount.com" --role="roles/storage.admin"
gcloud projects add-iam-policy-binding $GCP_PROJECT --member="serviceAccount:ccv-runner@$GCP_PROJECT.iam.gserviceaccount.com" --role="roles/aiplatform.user"
gcloud projects add-iam-policy-binding $GCP_PROJECT --member="serviceAccount:ccv-runner@$GCP_PROJECT.iam.gserviceaccount.com" --role="roles/logging.logWriter"
gcloud projects add-iam-policy-binding $GCP_PROJECT --member="serviceAccount:ccv-runner@$GCP_PROJECT.iam.gserviceaccount.com" --role="roles/monitoring.metricWriter"
(You may refine roles later — these are broad for initial deployment.)
5) Create GCS bucket for raw SCA and artifacts
BUCKET=ccv-raw-$GCP_PROJECT
gsutil mb -p $GCP_PROJECT -l us-central1 gs://$BUCKET
6) Create Pub/Sub topics
gcloud pubsub topics create ccv-analyze-finding
gcloud pubsub topics create ccv-run-scan
gcloud pubsub topics create ccv-sync-veracode
gcloud pubsub topics create ccv-embed-kb
(Optional) create normalization topic: ccv-normalize-report
7) Create Firestore database
In Console > Firestore create database (Native mode) in chosen region. Note project and database name (default: (default)).
Or via gcloud: follow Console prompt (Firestore creation cannot be fully scripted in one line).
8) Create Vertex AI Vector Search index (manual in Console or gcloud)
Via Console > Vertex AI > Vector Search: create index with dimension = settings.embed_dim (default 3072), distance = COSINE, deployed endpoint.
Note index id and endpoint; set them in app config later.
9) Prepare Docker images & containerize services
Services to deploy (suggested):
api_service (FastAPI) -> Cloud Run service: ccv-api
mcp_server -> Cloud Run: ccv-mcp
scan_runner (orchestrator / runner) -> Cloud Run service or Cloud Run Job: ccv-scan-runner
analysis_agent -> Cloud Run service or Cloud Run Job (subscriber): ccv-analysis-agent
kb_service -> Cloud Run service: ccv-kb
Create a Dockerfile at e.g. packages/api_service/Dockerfile (example below). Repeat for each service changing the working directory and entrypoint.
Example minimal Dockerfile (Python + Uvicorn):
FROM python:3.11-slimWORKDIR /appCOPY . /appRUN pip install --upgrade pip && pip install -r requirements.txt# for api_service, run uvicorn pointing to package moduleCMD ["uvicorn", "api_service.main:app", "--host", "0.0.0.0", "--port", "8080"]
Build & push images using Cloud Build (recommended):
gcloud builds submit --tag gcr.io/$GCP_PROJECT/ccv-api packages/api_service
gcloud builds submit --tag gcr.io/$GCP_PROJECT/ccv-mcp packages/mcp_server
gcloud builds submit --tag gcr.io/$GCP_PROJECT/ccv-scan-runner packages/scan_runner
gcloud builds submit --tag gcr.io/$GCP_PROJECT/ccv-analysis-agent packages/analysis_agent
gcloud builds submit --tag gcr.io/$GCP_PROJECT/ccv-kb packages/kb_service
10) Deploy services to Cloud Run
Example for API:
gcloud run deploy ccv-api --image gcr.io/$GCP_PROJECT/ccv-api --platform managed --region us-central1 --allow-unauthenticated \
--service-account=ccv-runner@$GCP_PROJECT.iam.gserviceaccount.com \
--set-env-vars FIRESTORE_PROJECT_ID=$GCP_PROJECT,FIRESTORE_DATABASE="(default)",PUBSUB_PROJECT_ID=$GCP_PROJECT,API_PORT=8080,GOOGLE_CLOUD_PROJECT=$GCP_PROJECT
Repeat for other services, set correct entrypoint env vars:
set PUBSUB topic names, Vertex index ids, GCS bucket name, VERACODE credentials in secret manager (see below).
11) Configure Pub/Sub push subscriptions (push to API endpoints)
Create push subscription for topic ccv-normalize-report pointing to API handler:
gcloud pubsub subscriptions create normalize-report-sub \
--topic=ccv-normalize-report \
--push-endpoint=https://ccv-api-<region>-run.app/pubsub/normalize-report \
--ack-deadline=60
For analysis, typically the Analysis Agent should subscribe (pull or push). Use push to Cloud Run endpoint /pubsub/analyze-finding or run Analysis Agent as subscriber pulling from subscription. Example push sub:
gcloud pubsub subscriptions create analyze-finding-sub \
--topic=ccv-analyze-finding \
--push-endpoint=https://ccv-api-<region>-run.app/pubsub/analyze-finding \
--ack-deadline=60
Note: Cloud Run endpoints require authentication — consider OIDC verification or configure push subscription with authentication (OIDC token) or make subscription call to a push endpoint that validates tokens. See docs: pubsub push to HTTPS with OIDC.
12) Secrets & environment configuration
Put sensitive items in Secret Manager (recommended): VERACODE_API_KEY_ID / SECRET, SERVICE_ACCOUNT_KEY if needed.
In Cloud Run, set env vars referring to secrets (or mount secrets via Env vars).
Minimum env vars include:
FIRESTORE_PROJECT_ID, FIRESTORE_DATABASE
PUBSUB_PROJECT_ID, PUBSUB_TOPIC_ANALYZE_FINDING, etc.
GCS_BUCKET (for raw SCA)
VECTOR_SEARCH_INDEX_ID, VECTOR_SEARCH_INDEX_ENDPOINT
GOOGLE_CLOUD_PROJECT
13) Run setup script to create example markers (optional)
If ADC or emulator configured, run:
python3 ccv/scripts/setup_firestore_schema.py
If running in Cloud Run, the deployed API will use Firestore automatically once configured.
14) Migrate data (if you have Postgres legacy)
Use ccv/scripts/pg_to_firestore.py (requires Postgres access) to migrate data -> Firestore and GCS embedding steps.
Run in controlled environment with ADC or service-account env.
15) Start the system and verify
Trigger a manual scan via API:
curl -X POST -H "Content-Type: application/json" -d '{"repo_id":"<repo_id>","branch":"main"}' https://<ccv-api-url>/api/scans/manual
This should:
create a ScanDoc in Firestore,
publish a run_scan message to Pub/Sub,
Cloud Run scan_runner service should pick it up (via push subscription) and start orchestrator workflow,
findings written to Firestore,
ANALYZE_FINDING messages published,
Analysis Agent consumes messages, writes FindingAnalysisDoc.
16) Cloud Scheduler (periodic Veracode sync)
Create Cloud Scheduler job to publish to ccv-sync-veracode topic every 5 minutes:
gcloud scheduler jobs create pubsub veracode-sync-job --schedule="/5 * * " --topic=ccv-sync-veracode --message-body='{}'
17) Monitoring & Logging
Use Cloud Monitoring & Cloud Logging to view logs for services, Pub/Sub metrics, Cloud Run metrics, and Vertex AI requests.
Add alerts for pub/sub backlog, high Firestore latency, Vertex errors.
18) Local development flow (emulators)
Start Firestore emulator:
gcloud beta emulators firestore start --host-port=localhost:8080
export FIRESTORE_EMULATOR_HOST=localhost:8080
export GOOGLE_CLOUD_PROJECT=local-project
Start Pub/Sub emulator:
gcloud beta emulators pubsub start --host-port=8085
export PUBSUB_EMULATOR_HOST=localhost:8085
Start services locally in .venv:
cd packages/api_service
. ../../.venv/bin/activate
python -m api_service.main
Use setup_firestore_schema.py (emulator mode) to create collections.
19) Post-deploy tasks
Create composite indexes from generated ccv/firestore.indexes.json via Console or gcloud firestore indexes create.
Configure Vertex index with correct dimensions and deploy.
Prune old vectors / implement a cleanup policy.
20) Troubleshooting checklist
If Firestore client errors: check ADC or FIRESTORE_EMULATOR_HOST.
If Pub/Sub push fails: check push endpoint and OIDC authentication settings; look at subscription push logs.
If Cloud Run returns 403: check service account and Cloud Run invoker IAM.
If Vertex upsert fails: check index dimension, model, and aiplatform permissions.
Quick minimal deploy example (commands summary)
Build API image:
gcloud builds submit --tag gcr.io/$GCP_PROJECT/ccv-api packages/api_service
Deploy API:
gcloud run deploy ccv-api --image gcr.io/$GCP_PROJECT/ccv-api --region us-central1 --allow-unauthenticated --service-account=ccv-runner@$GCP_PROJECT.iam.gserviceaccount.com --set-env-vars=FIRESTORE_PROJECT_ID=$GCP_PROJECT,FIRESTORE_DATABASE="(default)",PUBSUB_PROJECT_ID=$GCP_PROJECT,GCS_BUCKET=$BUCKET
Create Pub/Sub topics/subscriptions.
Build/deploy other services similarly.
If you want, I can next:
(A) Add example Dockerfile(s) and Cloud Build steps for each package and create a small deployment script.
(B) Implement the normalization worker and a Cloud Run Job definition (container + example).
(C) Produce exact env var file (.env.example) with all required variables and comments for Cloud Run.