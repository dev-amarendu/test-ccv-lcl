"""Repo listing and detail endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from google.cloud.firestore_v1 import AsyncClient
import httpx

from shared.config import get_settings

from shared.logging import get_logger
from shared.repositories.repos import RepoStore
from shared.schemas import RepoResponse

from api_service.deps import db_session

router = APIRouter(prefix="/repos", tags=["repos"])
logger = get_logger(__name__)


@router.get("", response_model=dict)
async def list_repos(
    external: str | None = Query(None, description="Set to 'bitbucket' to fetch from Bitbucket API"),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    db: AsyncClient = Depends(db_session),
) -> dict:
    """
    List repositories.

    By default returns repos from Firestore. If `external=bitbucket` and Bitbucket
    integration is enabled, fetch a live list from Bitbucket and return mapped items.
    """
    settings = get_settings()

    # Option A: live Bitbucket fetch
    if external == "bitbucket":
        if not settings.bitbucket_enabled:
            raise HTTPException(status_code=404, detail="Bitbucket integration not enabled")
        base = settings.bitbucket_base_url.rstrip("/")
        token = settings.bitbucket_token
        if not base or not token:
            raise HTTPException(status_code=400, detail="Bitbucket base URL or token not configured")

        # Call Bitbucket REST API (Server/Data Center) to list repos.
        # We request a reasonably large page; for production implement pagination.
        url = f"{base}/rest/api/1.0/repos"
        headers = {"Authorization": f"Bearer {token}"}
        params = {"limit": str(max(50, page_size))}
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get(url, headers=headers, params=params)
        if resp.status_code != 200:
            raise HTTPException(status_code=502, detail=f"Bitbucket API error: {resp.status_code}")
        data = resp.json()
        values = data.get("values", []) if isinstance(data, dict) else []
        items = []
        for r in values:
            # Defensive mapping for common fields
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

    # Default: Firestore-backed listing
    store = RepoStore(db)
    all_repos = await store.list_repos()
    total = len(all_repos)
    offset = (page - 1) * page_size
    page_items = all_repos[offset : offset + page_size]
    return {
        "items": [
            RepoResponse(
                id=r.id, org_id=r.org_id, name=r.name,
                default_branch=r.default_branch, connected=r.connected,
                created_at=r.created_at,
            ).model_dump(mode="json")
            for r in page_items
        ],
        "total": total,
        "page": page,
        "page_size": page_size,
    }


@router.get("/{repo_id}", response_model=RepoResponse)
async def get_repo(
    repo_id: str,
    db: AsyncClient = Depends(db_session),
) -> RepoResponse:
    """Get a single repo by id."""
    store = RepoStore(db)
    repo = await store.get_repo(repo_id)
    if not repo:
        raise HTTPException(status_code=404, detail="Repo not found")
    return RepoResponse(
        id=repo.id, org_id=repo.org_id, name=repo.name,
        default_branch=repo.default_branch, connected=repo.connected,
        created_at=repo.created_at,
    )
