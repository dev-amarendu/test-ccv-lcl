"""MCP internal bearer-token authentication."""

from __future__ import annotations

from fastapi import HTTPException

from shared.config import get_settings


def verify_mcp_token(auth_header: str) -> None:
    """Verify Authorization: Bearer <token> matches configured MCP_INTERNAL_TOKEN.

    If MCP_INTERNAL_TOKEN is not set or is the default placeholder, auth is
    skipped (useful for local dev).
    """
    settings = get_settings()
    expected = settings.mcp_internal_token

    # Skip auth in dev when token is placeholder
    if not expected or expected == "changeme":
        return

    if not auth_header.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or malformed Authorization header")

    token = auth_header[7:]
    if token != expected:
        raise HTTPException(status_code=403, detail="Invalid MCP token")
