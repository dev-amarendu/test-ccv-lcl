# GCP Component Verification Guide

This guide is designed for developers to verify access and functionality of the core GCP services used in the CCV project: **Firestore**, **Pub/Sub**, and **Vertex AI Vector Search**.

## Prerequisites

Ensure you have the Google Cloud SDK installed and authenticated.

```bash
# 1. Login
gcloud auth login
gcloud auth application-default login

# 2. Set your project ID
gcloud config set project YOUR_PROJECT_ID
```

---

## 1. Firestore (Database)

Firestore is the primary NoSQL database for CCV.

### A. Check Access via CLI
List the collections in the default database to verify read access.

```bash
gcloud firestore collections list --database="(default)"
```
*Expected Output*: A list of collections like `scans`, `repos`, `findings`, etc.

### B. Verify Write Access (Python Script)
Run this snippet to write and delete a test document.

**File:** `verify_firestore.py`
```python
import asyncio
from google.cloud import firestore

async def test_firestore():
    db = firestore.AsyncClient()
    doc_ref = db.collection("test_connectivity").document("ping")
    
    print("Writing test document...")
    await doc_ref.set({"status": "ok", "timestamp": firestore.SERVER_TIMESTAMP})
    
    print("Reading test document...")
    snap = await doc_ref.get()
    if snap.exists:
        print(f"Success! Read back: {snap.to_dict()}")
    else:
        print("Error: Document not found.")

    print("Deleting test document...")
    await doc_ref.delete()
    print("Done.")

if __name__ == "__main__":
    asyncio.run(test_firestore())
```

**Run it:**
```bash
python3 verify_firestore.py
```

---

## 2. Cloud Pub/Sub (Job Queue)

Pub/Sub handles asynchronous tasks (e.g., triggering scans, analyzing findings).

### A. Check Access via CLI
List the available topics.

```bash
gcloud pubsub topics list
```
*Expected Output*: You should see topics like `run-scan`, `analyze-finding`, `veracode-sync`.

### B. Verify Publish Access (Python Script)
Publish a dummy message to a test topic (or an existing one if safe).

**File:** `verify_pubsub.py`
```python
from google.cloud import pubsub_v1

def test_pubsub():
    publisher = pubsub_v1.PublisherClient()
    # Replace with your actual Project ID
    project_id = "YOUR_PROJECT_ID" 
    topic_id = "run-scan" # Using an existing topic
    
    topic_path = publisher.topic_path(project_id, topic_id)
    
    print(f"Publishing message to {topic_path}...")
    future = publisher.publish(topic_path, b'{"test": "ping"}')
    message_id = future.result()
    
    print(f"Success! Published message ID: {message_id}")

if __name__ == "__main__":
    test_pubsub()
```

**Run it:**
```bash
python3 verify_pubsub.py
```

---

## 3. Vertex AI Vector Search (RAG)

Vertex AI stores embeddings for Knowledge Base retrieval.

### A. Check Indexes via CLI
List the vector indexes to ensure you can see the infrastructure.

```bash
# List Indexes (replace region if different, e.g., us-central1)
gcloud ai indexes list --region=us-central1
```
*Expected Output*: You should see an index named `ccv-kb-index` (or similar).

### B. Verify Query Access
Querying requires a deployed endpoint. You can verify this storage Access using the Python SDK.

**File:** `verify_vertex.py`
```python
from google.cloud import aiplatform

def test_vertex_ai():
    # Initialize SDK
    aiplatform.init(location="us-central1") # Check your region
    
    print("Listing Vector Indexes...")
    indexes = aiplatform.MatchingEngineIndex.list()
    
    if not indexes:
        print("No indexes found. (Check permissions or region)")
        return

    for idx in indexes:
        print(f"Found Index: {idx.display_name} ({idx.resource_name})")
        
        # Check for Deployed Index endpoints
        for endpoint_name in idx.deployed_indexes:
             print(f" - Deployed to Endpoint: {endpoint_name}")

if __name__ == "__main__":
    test_vertex_ai()
```

**Run it:**
```bash
python3 verify_vertex.py
```

---

## Troubleshooting Common Errors

| Error | Cause | Fix |
|---|---|---|
| `DefaultCredentialsError` | Google Cloud SDK not authenticated. | Run `gcloud auth application-default login`. |
| `PermissionDenied` | Your IAM user lacks roles. | Ask admin to grant `Firestore User`, `Pub/Sub Editor`, or `Vertex AI User`. |
| `NotFound` | Resource doesn't exist or wrong Project ID. | Check `gcloud config get-value project` matches your target. |
