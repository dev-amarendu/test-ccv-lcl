"""KB store — Firestore access + Vertex AI Vector Search for Fix Cards."""

from __future__ import annotations

import asyncio
from typing import Any

from google.cloud import aiplatform

from shared.config import get_settings
from shared.firestore_client import get_firestore_client
from shared.firestore_models import KBFixCardDoc
from shared.logging import get_logger
from shared.repositories.kb_store import KBFixCardStore
from shared.utils import content_hash, generate_uuid

from kb_service.embeddings import embed_text

logger = get_logger(__name__)


async def get_fix_card(cwe_id: int) -> KBFixCardDoc | None:
    """Retrieve a Fix Card by CWE ID."""
    db = get_firestore_client()
    store = KBFixCardStore(db)
    return await store.get_by_cwe_id(cwe_id)


async def get_fix_card_by_id(card_id: str) -> KBFixCardDoc | None:
    """Retrieve a Fix Card by primary key."""
    db = get_firestore_client()
    store = KBFixCardStore(db)
    return await store.get_by_id(card_id)


async def list_fix_cards(page: int = 1, page_size: int = 50) -> tuple[list[KBFixCardDoc], int]:
    """List KB Fix Cards with pagination."""
    db = get_firestore_client()
    store = KBFixCardStore(db)
    return await store.list_cards(page, page_size)


async def upsert_fix_card(
    cwe_id: int,
    title: str,
    content: str,
    tags: list[str] | None = None,
    summary: str | None = None,
    fix_steps_json: dict | None = None,
    source: str = "CWE-660",
    embedding: list[float] | None = None,
    original_finding_id: str | None = None,
) -> KBFixCardDoc:
    """Insert or update a Fix Card."""
    settings = get_settings()
    db = get_firestore_client()
    store = KBFixCardStore(db)

    # Check if exists by CWE
    existing = await store.get_by_cwe_id(cwe_id)

    new_hash = content_hash(content)
    
    doc_id = existing.id if existing else str(generate_uuid())
    
    card = KBFixCardDoc(
        id=doc_id,
        cwe_id=cwe_id,
        title=title,
        content=content,
        tags=tags or [],
        summary=summary,
        fix_steps_json=fix_steps_json,
        source=source,
        content_hash=new_hash,
        original_finding_id=original_finding_id,
        embedding=embedding,
        embedding_model=settings.embedding_model if embedding else None,
        embedding_dim=len(embedding) if embedding else None,
        approved=True,
    )

    if existing:
        # Update existing
        update_data = card.model_dump(exclude={"created_at"}, exclude_unset=True)
        await store.update_card(doc_id, update_data)
        # Fetch updated to return full object
        return await store.get_by_id(doc_id) or card
    else:
        # Create new
        await store.upsert(card)
        return card


async def update_fix_card(card_id: str, **kwargs) -> KBFixCardDoc | None:
    """Partially update a Fix Card."""
    db = get_firestore_client()
    store = KBFixCardStore(db)

    card = await store.get_by_id(card_id)
    if not card:
        return None

    if "content" in kwargs and kwargs["content"]:
        kwargs["content_hash"] = content_hash(kwargs["content"])

    await store.update_card(card_id, kwargs)
    return await store.get_by_id(card_id)


async def increment_usage(card_id: str) -> None:
    """Increment usage_count for a Fix Card."""
    db = get_firestore_client()
    store = KBFixCardStore(db)
    await store.increment_usage(card_id)


async def vector_search(query_text: str, top_k: int = 5) -> list[dict[str, Any]]:
    """Perform vector similarity search using Vertex AI Vector Search.
    
    If Vector Search is not configured, fallback to Firestore simple filtering 
    (which won't be semantic) or return empty list.
    """
    settings = get_settings()
    
    # 1. Generate query embedding
    try:
        query_embedding = embed_text(query_text)
    except Exception as exc:
        logger.error("vector_search_embedding_failed", error=str(exc))
        return []

    # 2. Query Vertex AI Vector Search
    if not settings.vector_search_index_endpoint_id or not settings.vector_search_index_id:
        logger.warning("vector_search_not_configured")
        return []

    try:
        # Initialize Vertex AI SDK
        aiplatform.init(
            project=settings.firestore_project_id,
            location=settings.google_cloud_location,
        )

        my_index_endpoint = aiplatform.MatchingEngineIndexEndpoint(
            index_endpoint_name=settings.vector_search_index_endpoint_id
        )

        # Query the index
        # Note: public_endpoint_domain might be needed if using public endpoint
        response = my_index_endpoint.find_neighbors(
            deployed_index_id=settings.vector_search_deployed_index_id,
            queries=[query_embedding],
            num_neighbors=top_k,
        )

        if not response:
            return []

        # response is list[list[MatchNeighbor]]
        matches = response[0]
        
        # 3. Fetch full docs from Firestore based on IDs returned by Vector Search
        # We assume Vector Search stores the KBFixCardDoc ID as the datapoint ID
        results = []
        db = get_firestore_client()
        store = KBFixCardStore(db)
        
        # Collect IDs to fetch in parallel (or batch)
        # Firestore batch get is not directly exposed in our repo, looping for now or using internal method
        # Ideally KBFixCardStore should have get_batch(ids)
        
        for match in matches:
            card_id = match.id
            score = match.distance  # distance or similarity depending on config
            
            card = await store.get_by_id(card_id)
            if card:
                results.append({
                    "cwe_id": card.cwe_id,
                    "title": card.title,
                    "content": card.content,
                    "score": float(score),
                })
                
        return results

    except Exception as exc:
        logger.error("vertex_vector_search_failed", error=str(exc))
        return []


async def create_vector_index() -> None:
    """Trigger creation/update of Vertex AI Vector Search index.
    
    NOTE: This is a placeholder. Index management is usually done via IaC (Terraform)
    or separate scripts, not runtime application code.
    """
    logger.info("create_vector_index_called", msg="Manage indices via Terraform/Scripts")
