# GCP Service Account Setup Guide

To run the CCV project services (API, Scan Runner, Analysis Agent) with the service account JSON, follow these steps to create the account and assign the correct permissions.

## Steps

1. **Create the Service Account**:
   ```bash
   gcloud iam service-accounts create ccv-service-account \
       --display-name="CCV Service Account"
   ```

2. **Assign Required Roles**:
   Run these commands to grant the necessary permissions (replace `[PROJECT_ID]` with your GCP Project ID):
   
   *   **Firestore Access**:
       ```bash
       gcloud projects add-iam-policy-binding [PROJECT_ID] \
           --member="serviceAccount:ccv-service-account@[PROJECT_ID].iam.gserviceaccount.com" \
           --role="roles/datastore.user"
       ```
   *   **Pub/Sub Messaging**:
       ```bash
       gcloud projects add-iam-policy-binding [PROJECT_ID] \
           --member="serviceAccount:ccv-service-account@[PROJECT_ID].iam.gserviceaccount.com" \
           --role="roles/pubsub.publisher"
       
       gcloud projects add-iam-policy-binding [PROJECT_ID] \
           --member="serviceAccount:ccv-service-account@[PROJECT_ID].iam.gserviceaccount.com" \
           --role="roles/pubsub.subscriber"
       ```
   *   **Vertex AI (LLM / Embeddings)**:
       ```bash
       gcloud projects add-iam-policy-binding [PROJECT_ID] \
           --member="serviceAccount:ccv-service-account@[PROJECT_ID].iam.gserviceaccount.com" \
           --role="roles/aiplatform.user"
       ```
   *   **Cloud Run (Invocation)**:
       ```bash
       gcloud projects add-iam-policy-binding [PROJECT_ID] \
           --member="serviceAccount:ccv-service-account@[PROJECT_ID].iam.gserviceaccount.com" \
           --role="roles/run.invoker"
       ```
   *   **Secret Manager (Optional but recommended)**:
       ```bash
       gcloud projects add-iam-policy-binding [PROJECT_ID] \
           --member="serviceAccount:ccv-service-account@[PROJECT_ID].iam.gserviceaccount.com" \
           --role="roles/secretmanager.secretAccessor"
       ```

3. **Generate the JSON Key**:
   ```bash
   # Ensure you are in the project root ccv/ directory
   mkdir -p ./secrets
   gcloud iam service-accounts keys create ./secrets/sa-key.json \
       --iam-account=ccv-service-account@[PROJECT_ID].iam.gserviceaccount.com
   ```

4. **Update Environment**:
   Ensure `GOOGLE_APPLICATION_CREDENTIALS` in your `.env` points to this file:
   ```ini
   GOOGLE_APPLICATION_CREDENTIALS=./secrets/sa-key.json
   ```
