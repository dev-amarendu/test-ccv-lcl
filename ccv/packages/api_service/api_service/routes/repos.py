"""Repo listing and detail endpoints.

Endpoints:
- GET /repos?base_url=...&project=...       -> lists repository slugs for a project (async)
- GET /repos/{repo_id}?base_url=...         -> returns single repo metadata (async)

Both endpoints use BITBUCKET_TOKEN from environment and support an `insecure`
flag to disable SSL verification for self-signed Bitbucket Server instances.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query
import httpx
import os
from dotenv import load_dotenv
from typing import Optional, Dict, Any, List

from shared.logging import get_logger
from shared.schemas import RepoResponse

load_dotenv()  # load .env from project root for local/dev

router = APIRouter(prefix="/repos", tags=["repos"])
logger = get_logger(__name__)



async def _get_with_token(
    url: str, token: str, params: Optional[Dict[str, Any]] = None, verify_ssl: bool = True
) -> Optional[httpx.Response]:
    """Try async GET with both 'Bearer' and 'Token' auth schemes; return first non-auth-error response."""
    last_resp = None
    for scheme in ("Bearer", "Token"):
        headers = {"Accept": "application/json", "Authorization": f"{scheme} {token}"}
        async with httpx.AsyncClient(timeout=30, verify=verify_ssl) as client:
            resp = await client.get(url, headers=headers, params=params)
        last_resp = resp
        if resp.status_code in (401, 403):
            # auth failed for this scheme, try next
            continue
        return resp
    return last_resp


@router.get("", response_model=dict)
async def list_repos(
    base_url: Optional[str] = Query(None, description="Bitbucket base URL, e.g. https://bitbucket.example.com"),
    project: Optional[str] = Query(None, description="Project key, e.g. PROJ"),
    limit: int = Query(100, ge=1, le=1000, description="Page size per Bitbucket request"),
    insecure: bool = Query(False, description="Set true to disable SSL verification (self-signed certs)"),
) -> dict:
    """
    List repository slugs for a given Bitbucket Server/Data Center project.
    """
    token = os.getenv("BITBUCKET_TOKEN")
    if not token:
        raise HTTPException(status_code=500, detail="Missing BITBUCKET_TOKEN in environment")

    base = (base_url or os.getenv("BITBUCKET_BASE_URL") or "").rstrip("/")
    if not base:
        raise HTTPException(status_code=400, detail="Bitbucket base URL not provided via query or BITBUCKET_BASE_URL")
    api_url = f"{base}/rest/api/1.0/projects/{project}/repos" if project else f"{base}/rest/api/1.0/repos"

    repos: List[str] = []
    start = 0
    verify = not insecure

    while True:
        params = {"limit": limit, "start": start}
        resp = await _get_with_token(api_url, token, params=params, verify_ssl=verify)
        if resp is None:
            raise HTTPException(status_code=500, detail="No response received from Bitbucket")
        if resp.status_code in (401, 403):
            raise HTTPException(status_code=401, detail="Authentication failed (401/403)")
        if resp.status_code == 404:
            raise HTTPException(status_code=404, detail="Project not found (404)")
        try:
            resp.raise_for_status()
        except httpx.HTTPError as e:
            raise HTTPException(status_code=resp.status_code, detail=f"Bitbucket error: {str(e)}")
        data = resp.json()
        for r in data.get("values", []):
            repos.append(r.get("slug"))
        if data.get("isLastPage", True):
            break
        start = data.get("nextPageStart")
        if start is None:
            break
    return {"repositories": repos}


@router.get("/{repo_id}", response_model=RepoResponse)
async def get_repo(
    repo_id: str,
    base_url: Optional[str] = Query(None, description="Bitbucket base URL, e.g. https://bitbucket.example.com"),
    insecure: bool = Query(False, description="Set true to disable SSL verification (self-signed certs)"),
) -> RepoResponse:
    """
    Return a single repository's metadata from Bitbucket.
    Accepts `repo_id` as either 'slug' or 'PROJECT/slug'.
    """
    token = os.getenv("BITBUCKET_TOKEN")
    if not token:
        raise HTTPException(status_code=500, detail="Missing BITBUCKET_TOKEN in environment")
    base = (base_url or os.getenv("BITBUCKET_BASE_URL") or "").rstrip("/")
    if not base:
        raise HTTPException(status_code=400, detail="Bitbucket base URL not provided via query or BITBUCKET_BASE_URL")
    verify = not insecure

    # If repo_id is provided as "PROJECT/slug", use the project-specific endpoint
    if "/" in repo_id:
        project, slug = repo_id.split("/", 1)
        url = f"{base}/rest/api/1.0/projects/{project}/repos/{slug}"
        resp = await _get_with_token(url, token, params=None, verify_ssl=verify)
        if resp and resp.status_code == 200:
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

    # Otherwise, list repos and match by slug/name/id
    url = f"{base}/rest/api/1.0/repos"
    params = {"limit": 1000}
    resp = await _get_with_token(url, token, params=params, verify_ssl=verify)
    if resp is None:
        raise HTTPException(status_code=502, detail="Bitbucket API error")
    if resp.status_code != 200:
        raise HTTPException(status_code=502, detail=f"Bitbucket API error: {resp.status_code}")
    data = resp.json()
    for r in data.get("values", []):
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
