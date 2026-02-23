"""Test KB Fix Cards — templates, hashing, and mock embedding."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from kb_service.templates import generate_fix_card_content
from shared.utils import content_hash


class TestFixCardTemplate:
    def test_template_generates_content(self):
        content = generate_fix_card_content(cwe_id=79, cwe_name="Cross-Site Scripting")
        assert "CWE-79" in content
        assert "Cross-Site Scripting" in content

    def test_template_is_deterministic(self):
        c1 = generate_fix_card_content(cwe_id=89, cwe_name="SQL Injection")
        c2 = generate_fix_card_content(cwe_id=89, cwe_name="SQL Injection")
        assert c1 == c2

    def test_template_includes_mitigations(self):
        content = generate_fix_card_content(
            cwe_id=79, cwe_name="XSS",
            potential_mitigations="Use output encoding. Apply CSP headers.",
        )
        assert "output encoding" in content

    def test_template_includes_references(self):
        content = generate_fix_card_content(cwe_id=79, cwe_name="XSS")
        assert "cwe.mitre.org" in content


class TestContentHash:
    def test_hash_is_deterministic(self):
        assert content_hash("test") == content_hash("test")

    def test_different_content_different_hash(self):
        assert content_hash("A") != content_hash("B")


class TestEmbeddingGeneration:
    @patch("kb_service.embeddings.get_embedding_client")
    def test_embed_text_returns_vector(self, mock_get_client):
        from kb_service.embeddings import embed_text

        dim = 768
        mock_embedding = MagicMock()
        mock_embedding.values = [0.1] * dim
        mock_response = MagicMock()
        mock_response.embeddings = [mock_embedding]
        mock_client = MagicMock()
        mock_client.models.embed_content.return_value = mock_response
        mock_get_client.return_value = mock_client

        result = embed_text("Test", dimensions=dim)
        assert len(result) == dim
        assert all(isinstance(x, float) for x in result)

    @patch("kb_service.embeddings.get_embedding_client")
    def test_embed_texts_batch(self, mock_get_client):
        from kb_service.embeddings import embed_texts_batch

        dim = 768
        mock_embedding = MagicMock()
        mock_embedding.values = [0.2] * dim
        mock_response = MagicMock()
        mock_response.embeddings = [mock_embedding, mock_embedding]
        mock_client = MagicMock()
        mock_client.models.embed_content.return_value = mock_response
        mock_get_client.return_value = mock_client

        results = embed_texts_batch(["t1", "t2"], dimensions=dim)
        assert len(results) == 2


class TestKBStoreContract:
    def test_fix_card_content_can_be_hashed(self):
        content = generate_fix_card_content(cwe_id=89, cwe_name="SQL Injection")
        h = content_hash(content)
        assert len(h) == 64
        assert h == content_hash(content)
