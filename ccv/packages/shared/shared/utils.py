"""Shared utility helpers."""

from __future__ import annotations

import hashlib
import json
import uuid
from typing import Any


def generate_uuid() -> uuid.UUID:
    return uuid.uuid4()


def stable_fingerprint(*parts: str) -> str:
    """Create a deterministic SHA-256 fingerprint from ordered parts.

    Used to deduplicate findings across scans.  Typical usage::

        fingerprint = stable_fingerprint(str(cwe_id), file_path, str(line), title)
    """
    # Defensive: coerce every part to a flat string even if a list/dict sneaks in
    raw = "|".join(str(p) for p in parts)
    return hashlib.sha256(raw.encode()).hexdigest()


def content_hash(text: str) -> str:
    """SHA-256 hash of arbitrary text (used for KB content dedup)."""
    return hashlib.sha256(text.encode()).hexdigest()


def safe_json_dumps(obj: Any) -> str:
    """JSON-encode with fallback for non-serializable objects."""
    try:
        return json.dumps(obj, default=str, ensure_ascii=False)
    except (TypeError, ValueError):
        return "{}"


def paginate_query_params(page: int = 1, page_size: int = 50) -> tuple[int, int]:
    """Return (offset, limit) from 1-based page params."""
    page = max(1, page)
    page_size = max(1, min(page_size, 200))
    return (page - 1) * page_size, page_size
