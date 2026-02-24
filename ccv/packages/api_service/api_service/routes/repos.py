"""Repo listing and detail endpoints."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query
import httpx

from shared.config import get_settings
from shared.logging import get_logger
from shared.schemas import RepoResponse

router = APIRouter(prefix="/repos", tags=["repos"])
logger = get_logger(__name__)


@router.get("", response_model=dict)
async def list_repos(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
) -> dict:
    """
    List repositories by querying Bitbucket live. Firestore is not used for repo listing.
    """
    settings = get_settings()
    if not settings.bitbucket_enabled:
        raise HTTPException(status_code=404, detail="Bitbucket integration not enabled")
    base = settings.bitbucket_base_url.rstrip("/")
    token = settings.bitbucket_token
    if not base or not token:
        raise HTTPException(status_code=400, detail="Bitbucket base URL or token not configured")

    url = f"{base}/rest/api/1.0/repos"
    headers = {"Authorization": f"Bearer {token}"}
    params = {"limit": str(max(100, page_size))}
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.get(url, headers=headers, params=params)
    if resp.status_code != 200:
        raise HTTPException(status_code=502, detail=f"Bitbucket API error: {resp.status_code}")
    data = resp.json()
    values = data.get("values", []) if isinstance(data, dict) else []
    items = []
    for r in values:
        repo_id = str(r.get("slug") or r.get("id") or r.get("name"))
        name = r.get("name") or r.get("slug") or repo_id
        default_branch = ""
        try:
            default_branch = r.get("defaultBranch", {}).get("displayId", "") or ""
        except Exception:
            default_branch = ""
        items.append({
            "id": repo_id,
            "org_id": r.get("project", {}).get("key", "bitbucket"),
            "name": name,
            "default_branch": default_branch or "main",
            "connected": True,
            "created_at": r.get("createdDate") or r.get("metadata", {}).get("createdDate"),
        })
    total = len(items)
    offset = (page - 1) * page_size
    page_items = items[offset : offset + page_size]
    return {"items": page_items, "total": total, "page": page, "page_size": page_size}


@router.get("/{repo_id}", response_model=RepoResponse)
async def get_repo(
    repo_id: str,
) -> RepoResponse:
    """Get a single repo by id (live from Bitbucket)."""
    settings = get_settings()
    if not settings.bitbucket_enabled:
        raise HTTPException(status_code=404, detail="Bitbucket integration not enabled")
    base = settings.bitbucket_base_url.rstrip("/")
    token = settings.bitbucket_token
    if not base or not token:
        raise HTTPException(status_code=400, detail="Bitbucket base URL or token not configured")

    headers = {"Authorization": f"Bearer {token}"}
    # If repo_id is provided as "PROJECT/slug", use the project-specific endpoint
    if "/" in repo_id:
        project, slug = repo_id.split("/", 1)
        url = f"{base}/rest/api/1.0/projects/{project}/repos/{slug}"
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get(url, headers=headers)
        if resp.status_code == 200:
            r = resp.json()
            repo_id_val = str(r.get("slug") or r.get("id") or r.get("name"))
            return RepoResponse(
                id=repo_id_val,
                org_id=r.get("project", {}).get("key", "bitbucket"),
                name=r.get("name") or repo_id_val,
                default_branch=r.get("defaultBranch", {}).get("displayId", "") or "main",
                connected=True,
                created_at=r.get("createdDate"),
            )
        raise HTTPException(status_code=404, detail="Repo not found in Bitbucket")

    # Otherwise, attempt to find by slug or name by listing repos and matching
    url = f"{base}/rest/api/1.0/repos"
    params = {"limit": "1000"}
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.get(url, headers=headers, params=params)
    if resp.status_code != 200:
        raise HTTPException(status_code=502, detail=f"Bitbucket API error: {resp.status_code}")
    data = resp.json()
    values = data.get("values", []) if isinstance(data, dict) else []
    for r in values:
        if repo_id in (str(r.get("slug")), str(r.get("name")), str(r.get("id"))):
            repo_id_val = str(r.get("slug") or r.get("id") or r.get("name"))
            return RepoResponse(
                id=repo_id_val,
                org_id=r.get("project", {}).get("key", "bitbucket"),
                name=r.get("name") or repo_id_val,
                default_branch=r.get("defaultBranch", {}).get("displayId", "") or "main",
                connected=True,
                created_at=r.get("createdDate"),
            )
    raise HTTPException(status_code=404, detail="Repo not found")
