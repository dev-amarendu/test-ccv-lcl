"""Vertex AI embedding client using google-genai SDK with ADC auth."""

from __future__ import annotations

import os
from typing import Any

from shared.config import get_settings
from shared.logging import get_logger

logger = get_logger(__name__)


def _ensure_vertex_env() -> None:
    """Set env vars for google-genai Vertex AI mode."""
    settings = get_settings()
    os.environ.setdefault("GOOGLE_CLOUD_PROJECT", settings.google_cloud_project)
    os.environ.setdefault("GOOGLE_CLOUD_LOCATION", settings.google_cloud_location)
    os.environ.setdefault("GOOGLE_GENAI_USE_VERTEXAI", str(settings.google_genai_use_vertexai).lower())


def get_embedding_client():
    """Return a configured google.genai.Client for embeddings."""
    _ensure_vertex_env()
    from google import genai
    from google.genai import types

    return genai.Client(http_options=types.HttpOptions(api_version="v1"))


def embed_text(text: str, model: str | None = None, dimensions: int | None = None) -> list[float]:
    """Generate an embedding vector for the given text.

    Args:
        text: The text to embed.
        model: Embedding model name (defaults to settings.embedding_model).
        dimensions: Output dimensions (defaults to settings.embed_dim).

    Returns:
        A list of floats representing the embedding vector.
    """
    settings = get_settings()
    model = model or settings.embedding_model
    dimensions = dimensions or settings.embed_dim

    client = get_embedding_client()

    from google.genai import types

    config = types.EmbedContentConfig(output_dimensionality=dimensions)
    response = client.models.embed_content(
        model=model,
        contents=text,
        config=config,
    )

    embedding = response.embeddings[0].values
    logger.info("embedding_generated", model=model, dim=len(embedding), input_chars=len(text))
    return list(embedding)


def embed_texts_batch(texts: list[str], model: str | None = None, dimensions: int | None = None) -> list[list[float]]:
    """Generate embeddings for a batch of texts.

    Args:
        texts: List of texts to embed.
        model: Embedding model name.
        dimensions: Output dimensions.

    Returns:
        List of embedding vectors.
    """
    settings = get_settings()
    model = model or settings.embedding_model
    dimensions = dimensions or settings.embed_dim

    client = get_embedding_client()

    from google.genai import types

    config = types.EmbedContentConfig(output_dimensionality=dimensions)

    results = []
    # Process in batches of 100 (API limit)
    batch_size = 100
    for i in range(0, len(texts), batch_size):
        batch = texts[i : i + batch_size]
        response = client.models.embed_content(
            model=model,
            contents=batch,
            config=config,
        )
        for emb in response.embeddings:
            results.append(list(emb.values))

    logger.info("batch_embeddings_generated", model=model, count=len(results))
    return results
