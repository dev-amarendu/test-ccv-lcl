"""Bitbucket MCP tool — minimal PR metadata retrieval."""

from __future__ import annotations

from typing import Any

import httpx

from shared.config import get_settings
from shared.logging import get_logger

logger = get_logger(__name__)


async def bitbucket_get_pull_request(params: dict[str, Any]) -> dict:
    """Fetch minimal pull request metadata from Bitbucket.

    Params:
        project: str — Bitbucket project key
        repo_slug: str — repository slug
        pr_id: int — pull request ID
    """
    settings = get_settings()

    if not settings.bitbucket_enabled:
        return {"error": "Bitbucket integration is disabled"}

    base = settings.bitbucket_base_url.rstrip("/")
    project = params["project"]
    repo_slug = params["repo_slug"]
    pr_id = params["pr_id"]

    url = f"{base}/rest/api/1.0/projects/{project}/repos/{repo_slug}/pull-requests/{pr_id}"

    headers = {}
    if settings.bitbucket_token:
        headers["Authorization"] = f"Bearer {settings.bitbucket_token}"

    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.get(url, headers=headers)

    resp.raise_for_status()
    data = resp.json()

    return {
        "id": data.get("id"),
        "title": data.get("title"),
        "state": data.get("state"),
        "source_branch": data.get("fromRef", {}).get("displayId"),
        "target_branch": data.get("toRef", {}).get("displayId"),
        "author": data.get("author", {}).get("user", {}).get("name"),
    }
