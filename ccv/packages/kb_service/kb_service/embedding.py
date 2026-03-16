

import os
import json
import time
import uuid
import logging
from dataclasses import dataclass
from typing import List, Dict, Any, Optional

# Google Cloud / Vertex AI
from google.cloud import aiplatform
from google.cloud import storage
from google.oauth2 import service_account
import vertexai
from vertexai.language_models import TextEmbeddingModel
from google.api_core.exceptions import GoogleAPIError

# Your shared configuration
from shared.config import get_settings
# ============================================================
# Settings
# ============================================================
_settings = get_settings()

# ---------------------------------------------------------------------
# Globals (lazily initialized)
# ---------------------------------------------------------------------
_aiplatform_initialized = False
_storage_client: Optional[storage.Client] = None
_embedding_model_instance: Optional[TextEmbeddingModel] = None

# ---------------------------------------------------------------------
# Initialization
# ---------------------------------------------------------------------
def _initialize_gcp_clients_with_sa():
    """Initialize Vertex AI (aiplatform & vertexai) and GCS with a service account."""
    global _aiplatform_initialized, _storage_client

    if _aiplatform_initialized:
        return

    if not os.path.exists(_settings.google_application_credentials):
        raise FileNotFoundError(
            f"Service account key file missing: '{_settings.google_application_credentials}'. "
            f"Set GOOGLE_APPLICATION_CREDENTIALS or place the key file accordingly."
        )

    credentials_obj = service_account.Credentials.from_service_account_file(
        _settings.google_application_credentials
    )

    # Vertex AI Admin (aiplatform) + Vertex SDK (vertexai)
    aiplatform.init(
        project=_settings.firestore_project_id,
        location=_settings.google_cloud_location,
        credentials=credentials_obj
    )
    vertexai.init(
        project=_settings.firestore_project_id,
        location=_settings.google_cloud_location,
        credentials=credentials_obj
    )
    logger.info("Vertex AI initialized for project '%s' in region '%s'.",
                _settings.firestore_project_id, _settings.google_cloud_location)

    # GCS client
    _storage_client = storage.Client(
        project=_settings.firestore_project_id,
        credentials=credentials_obj
    )
    logger.info("GCS client initialized.")

    _aiplatform_initialized = True

# ---------------------------------------------------------------------
# Embedding model & chunking
# ---------------------------------------------------------------------
def _get_embedding_model_instance() -> TextEmbeddingModel:
    global _embedding_model_instance
    if _embedding_model_instance is None:
        _initialize_gcp_clients_with_sa()
        _embedding_model_instance = TextEmbeddingModel.from_pretrained(_settings.embedding_model)
        logger.info("Embedding model '%s' loaded.", _settings.embedding_model)
    return _embedding_model_instance

def _chunk_text(text: str, chunk_size_tokens: int, chunk_overlap_tokens: int) -> List[str]:
    """
    Splits text into chunks based on token count, with overlap.
    Ensures each chunk is within model's max input token limit.
    """
    model_instance = _get_embedding_model_instance()

    chunks: List[str] = []
    current = text

    effective_chunk_size = min(chunk_size_tokens, _settings.max_embedding_input_tokens)
    effective_overlap = min(
        chunk_overlap_tokens,
        effective_chunk_size - 1 if effective_chunk_size > 1 else 0
    )
    approx_chars_per_token = 4

    while current:
        candidate_len = min(len(current), effective_chunk_size * approx_chars_per_token)
        chunk = current[:candidate_len]

        # shrink if token count > max
        while True:
            try:
                token_count = model_instance.count_tokens([chunk]).total_tokens
            except Exception as e:
                logger.warning("Token count failed (%s); truncating aggressively.", e)
                token_count = _settings.max_embedding_input_tokens + 1

            if token_count <= _settings.max_embedding_input_tokens:
                break

            new_len = len(chunk) * (_settings.max_embedding_input_tokens / token_count) - 100
            if new_len <= 0:
                logger.warning("Cannot reduce chunk further; skipping this portion.")
                chunk = ""
                break
            chunk = chunk[:int(new_len)]
            if len(chunk) < 50:
                logger.warning("Chunk became too small; skipping.")
                chunk = ""
                break

        if chunk:
            chunks.append(chunk)

        move_chars = len(chunk) - (effective_overlap * approx_chars_per_token)
        if move_chars < 0:
            move_chars = 0
        current = current[move_chars:]

        # Early stop for tiny trailing tail
        if len(current) < (effective_chunk_size * approx_chars_per_token / 4) and len(current) < 50:
            break

    if not chunks and text:
        # Fallback: single truncated chunk
        chunks.append(text[:_settings.max_embedding_input_tokens * approx_chars_per_token])

    return chunks

def embed_texts(texts: List[str]) -> List[List[float]]:
    """Batch-embed a list of texts using Vertex AI TextEmbeddingModel."""
    if not texts:
        return []

    model_instance = _get_embedding_model_instance()
    all_embeddings: List[List[float]] = []

    total = len(texts)
    bs = _settings.embedding_batch_size
    for i in range(0, total, bs):
        batch = texts[i: i + bs]
        logger.info("Embedding batch %s/%s (size %s)",
                    (i // bs) + 1, (total + bs - 1) // bs, len(batch))
        try:
            responses = model_instance.get_embeddings(batch)
            for resp in responses:
                all_embeddings.append(resp.values if resp and resp.values else [])
            # light pacing to avoid rate spikes
            time.sleep(1)
        except Exception:
            logger.exception("Embedding batch failed.")
            raise

    if all_embeddings and all_embeddings[0]:
        logger.info("Embeddings generated: %s total; dim: %s", len(all_embeddings), len(all_embeddings[0]))
    else:
        logger.info("Embeddings generated: %s total; first dim: N/A", len(all_embeddings))

    return all_embeddings

# ---------------------------------------------------------------------
# GCS helpers
# ---------------------------------------------------------------------
def _ensure_bucket_region_matches_vertex(bucket_name: str, vertex_region: str):
    """Ensure the bucket exists and is in the same region as Vertex AI; create if missing."""
    _initialize_gcp_clients_with_sa()
    try:
        bucket = _storage_client.get_bucket(bucket_name)
        bucket_loc = (bucket.location or "").lower()
        if bucket_loc != vertex_region.lower():
            raise ValueError(
                f"GCS bucket '{bucket_name}' is in '{bucket_loc}', but Vertex location is '{vertex_region}'. "
                f"Create/use a regional bucket in '{vertex_region}'."
            )
    except GoogleAPIError as e:
        if getattr(e, "code", None) == 404:
            logger.info("Bucket '%s' not found; creating in '%s'...", bucket_name, vertex_region)
            bucket = _storage_client.create_bucket(bucket_name, location=vertex_region)
            logger.info("Bucket '%s' created.", bucket_name)
        else:
            logger.exception("Error while checking/creating bucket '%s'.", bucket_name)
            raise

def _upload_to_gcs(bucket_name: str, source_file_name: str, destination_blob_name: str) -> str:
    """Upload a local file to GCS after region guard."""
    _ensure_bucket_region_matches_vertex(bucket_name, _settings.google_cloud_location)
    bucket = _storage_client.get_bucket(bucket_name)
    blob = bucket.blob(destination_blob_name)
    blob.upload_from_filename(source_file_name)
    gcs_uri = f"gs://{bucket_name}/{destination_blob_name}"
    logger.info("Uploaded '%s' -> '%s'", source_file_name, gcs_uri)
    return gcs_uri

def _gcs_dir_uri_from_file(gcs_uri: str) -> str:
    """Convert 'gs://bucket/path/file.json' -> 'gs://bucket/path/' (directory ingest)."""
    if not gcs_uri.startswith("gs://"):
        raise ValueError(f"Invalid GCS URI: {gcs_uri}")
    if gcs_uri.endswith("/"):
        return gcs_uri
    parts = gcs_uri.split("/")
    if len(parts) <= 4:
        # 'gs://bucket/file.json' -> 'gs://bucket/'
        return "/".join(parts[:3]) + "/"
    return "/".join(parts[:-1]) + "/"

# ---------------------------------------------------------------------
# Index / Endpoint helpers
# ---------------------------------------------------------------------
def _create_or_update_index(
    index_display_name: str,
    gcs_dir_uri: str,
    dimensions: int,
    description: str,
    overwrite: bool,
) -> aiplatform.MatchingEngineIndex:
    """
    Creates (Tree-AH) or updates an index. For updates, we pass contents_delta_uri.
    """
    existing = aiplatform.MatchingEngineIndex.list(filter=f'display_name="{index_display_name}"')
    if existing:
        index = existing[0]
        logger.info("Index '%s' exists. Updating (overwrite=%s)...", index_display_name, overwrite)
        op = index.update_embeddings(
            contents_delta_uri=gcs_dir_uri,
            is_complete_overwrite=bool(overwrite)
        )
        op.wait()
        return index

    logger.info("Creating new index '%s'...", index_display_name)
    index = aiplatform.MatchingEngineIndex.create_tree_ah_index(
        display_name=index_display_name,
        contents_delta_uri=gcs_dir_uri,
        dimensions=dimensions,
        approximate_neighbors_count=_settings.approximate_neighbors_count,
        distance_measure_type="DOT_PRODUCT_DISTANCE",
        feature_norm_type="UNIT_L2_NORM",  # optional; remove to disable normalization
        description=description,
        project=_settings.firestore_project_id,
        location=_settings.google_cloud_location,
    )
    index.wait()
    logger.info("Index created: %s", index.name)
    return index

def _deploy_index_to_endpoint(index: aiplatform.MatchingEngineIndex) -> aiplatform.MatchingEngineIndexEndpoint:
    """Idempotently deploy index to an endpoint (public)."""
    endpoint_display_name = f"{index.display_name}-endpoint"
    existing_endpoints = aiplatform.MatchingEngineIndexEndpoint.list(
        filter=f'display_name="{endpoint_display_name}"'
    )
    if existing_endpoints:
        endpoint = existing_endpoints[0]
        logger.info("Endpoint '%s' exists: %s", endpoint_display_name, endpoint.name)
        if any(d.index == index.resource_name for d in endpoint.deployed_indexes):
            logger.info("Index already deployed to this endpoint.")
            return endpoint
        logger.info("Deploying index to existing endpoint...")
        op = endpoint.deploy_index(
            index=index,
            deployed_index_id=f"deployed_{index.resource_name.split('/')[-1]}_{uuid.uuid4().hex[:8]}",
            machine_type="e2-standard-2",
            min_replica_count=1,
            max_replica_count=2,
        )
        op.wait()
        logger.info("Index deployed.")
        return endpoint

    logger.info("Creating endpoint '%s' and deploying index (Private VPC)...", endpoint_display_name)
    endpoint = aiplatform.MatchingEngineIndexEndpoint.create(
        display_name=endpoint_display_name,
        project=_settings.firestore_project_id,
        location=_settings.google_cloud_location,
        public_endpoint_enabled=False,
        network=_settings.vector_search_network if _settings.vector_search_network else None
    )
    endpoint.wait()
    op = endpoint.deploy_index(
        index=index,
        deployed_index_id=f"deployed_{index.resource_name.split('/')[-1]}_{uuid.uuid4().hex[:8]}",
        machine_type="e2-standard-2",
        min_replica_count=1,
        max_replica_count=2,
    )
    op.wait()
    logger.info("Index deployed to new endpoint.")
    return endpoint

# ---------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------
def store_embeddings_from_metadata(
    items: List[Dict[str, Any]],
    *,
    index_display_name: Optional[str] = None,
    index_description: Optional[str] = None,
    overwrite: bool = False,
) -> Dict[str, Any]:
    """
    Ingests items shaped like:
      items = [
        {
          "id": "doc-001",
          "metadata": {...},   # any JSON-serializable object (we normalize types)
          "text": "override text to embed"  # optional; if absent, text built from metadata
        },
        ...
      ]

    Returns:
      {
        "index_id": <resource name>,
        "endpoint_id": <resource name>,
        "gcs_uri": "gs://bucket/path/file.json",
        "ingested_count": <int>
      }
    """
    if not items:
        logger.warning("No items provided; returning empty result.")
        return {"index_id": "", "endpoint_id": "", "gcs_uri": "", "ingested_count": 0}

    _initialize_gcp_clients_with_sa()

    index_display_name = index_display_name or _settings.vector_search_index_display_name
    index_description = index_description or _settings.vector_search_index_description

    # 1) Prepare chunks (id, text_to_embed, metadata)
    prepared_chunks: List[Dict[str, Any]] = []
    model_instance = _get_embedding_model_instance()

    def _normalize(v):
        if isinstance(v, dict):
            return {k: _normalize(vv) for k, vv in v.items()}
        if isinstance(v, list):
            return [_normalize(x) for x in v]
        if hasattr(v, "isoformat"):
            try:
                return v.isoformat()
            except Exception:
                return str(v)
        if isinstance(v, (str, int, float, bool)) or v is None:
            return v
        return str(v)

    for n, it in enumerate(items, start=1):
        item_id = it.get("id")
        raw_meta = it.get("metadata") or {}
        text_source = it.get("text")

        if not item_id:
            logger.warning("[%s] Missing 'id'—skipping.", n)
            continue

        meta_norm = _normalize(raw_meta)

        if not text_source or not isinstance(text_source, str) or not text_source.strip():
            # Minimal fallback if caller doesn't supply 'text'
            # (prefer your API to provide a well-structured 'text' already)
            # Build a shallow text from key fields if they exist:
            key_order = ["title", "summary", "risk", "content"]
            buf = []
            for k in key_order:
                if k in meta_norm and isinstance(meta_norm[k], str):
                    buf.append(f"{k.capitalize()}: {meta_norm[k]}")
            if not buf:
                buf.append(json.dumps(meta_norm, ensure_ascii=False))
            text_source = "\n".join(buf)

        # Chunk if too long
        try:
            num_tokens = model_instance.count_tokens([text_source]).total_tokens
        except Exception as e:
            logger.warning("[%s] Token count failed (%s). Forcing chunk path.", n, e)
            num_tokens = _settings.chunk_text_if_longer_than_tokens + 1

        if num_tokens > _settings.chunk_text_if_longer_than_tokens:
            chunks = _chunk_text(text_source, _settings.chunk_size_tokens, _settings.chunk_overlap_tokens)
        else:
            chunks = [text_source]

        for i, ch in enumerate(chunks):
            prepared_chunks.append({
                "id": f"{item_id}-c{i}",
                "text_to_embed": ch,
                "metadata": {**meta_norm, "_chunk_index": i}
            })

    if not prepared_chunks:
        logger.warning("No chunks prepared; returning empty result.")
        return {"index_id": "", "endpoint_id": "", "gcs_uri": "", "ingested_count": 0}

    # 2) Embed
    texts_to_embed = [x["text_to_embed"] for x in prepared_chunks]
    logger.info("Embedding %s chunk(s)...", len(texts_to_embed))
    embeddings = embed_texts(texts_to_embed)

    # 3) Build final records
    final_records = []
    for i, obj in enumerate(prepared_chunks):
        if i < len(embeddings) and embeddings[i]:
            final_records.append({
                "id": obj["id"],
                "embedding": embeddings[i],
                "restricts": [],
                "metadata": obj["metadata"]
            })
        else:
            logger.warning("Dropping id=%s due to empty embedding.", obj["id"])

    if not final_records:
        logger.warning("No valid embeddings; returning empty result.")
        return {"index_id": "", "endpoint_id": "", "gcs_uri": "", "ingested_count": 0}

    # 4) Write JSON-lines with .json extension
    json_filename = f"vector_search_input_{int(time.time())}_{uuid.uuid4().hex[:6]}.json"
    local_json_path = os.path.join(os.getcwd(), json_filename)
    with open(local_json_path, "w", encoding="utf-8") as f:
        for rec in final_records:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    logger.info("Wrote %s records to %s", len(final_records), local_json_path)

    # 5) Upload to GCS
    gcs_input_uri = _upload_to_gcs(
        _settings.gcs_bucket_name,
        local_json_path,
        f"vector_search_input/{json_filename}"
    )
    try:
        os.remove(local_json_path)
    except Exception:
        pass

    # 6) Convert to directory URI for ingest
    gcs_dir_uri = _gcs_dir_uri_from_file(gcs_input_uri)

    # 7) Create/update index
    embedding_dimensions = len(final_records[0]["embedding"])
    index = _create_or_update_index(
        index_display_name=index_display_name,
        gcs_dir_uri=gcs_dir_uri,
        dimensions=embedding_dimensions,
        description=index_description,
        overwrite=bool(overwrite or _settings.index_overwrite_default),
    )

    # 8) Deploy to endpoint (idempotent)
    endpoint = _deploy_index_to_endpoint(index)

    return {
        "index_id": index.name,
        "endpoint_id": endpoint.name,
        "gcs_uri": gcs_input_uri,
        "ingested_count": len(final_records),
    }