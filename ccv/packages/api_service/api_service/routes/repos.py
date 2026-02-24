"""Repo listing endpoints — fetches directly from Bitbucket Server/DC.

Endpoints:
- GET /repos?base_url=...&project=...       -> lists repository slugs for a project
- GET /repos/{repo_id}?base_url=...         -> returns single repo metadata
"""

from __future__ import annotations

import os
from typing import Optional, Dict, Any, List

import requests
from fastapi import APIRouter, HTTPException, Query
from dotenv import load_dotenv

from shared.logging import get_logger
from shared.schemas import RepoResponse

load_dotenv()

router = APIRouter(prefix="/repos", tags=["repos"])
logger = get_logger(__name__)


def _make_headers(token: str, scheme: str) -> dict:
    return {
        "Accept": "application/json",
        "Authorization": f"{scheme} {token}",
    }


def _get_with_token(
    url: str,
    token: str,
    params: Optional[dict] = None,
    verify_ssl: bool = True,
) -> requests.Response:
    """
    Try Bearer first, then Token. Many Bitbucket DC instances accept Bearer for PAT,
    but some expect Token.
    """
    last_resp = None

    for scheme in ("Bearer", "Token"):
        headers = _make_headers(token, scheme)
        resp = requests.get(
            url,
            headers=headers,
            params=params,
            timeout=30,
            verify=verify_ssl,
        )
        last_resp = resp

        if resp.status_code in (401, 403):
            continue

        return resp

    return last_resp


# ── GET / — list repos from Bitbucket ────────────────────────────────────────


@router.get("", response_model=list[RepoResponse])
def list_repos(
    base_url: Optional[str] = Query(None, description="Bitbucket base URL, e.g. https://coxrepo.corp.cox.com/stash"),
    project: Optional[str] = Query(None, description="Project key, e.g. CCPT-DA"),
    limit: int = Query(100, ge=1, le=1000),
    insecure: bool = Query(False, description="Set true to disable SSL verification (self-signed certs)"),
) -> list[RepoResponse]:
    """
    Lists repositories under a given Bitbucket Server/DC project.
    Returns full repo objects.
    """
    base = (base_url or os.getenv("BITBUCKET_BASE_URL") or "").rstrip("/")
    if not base:
        raise HTTPException(status_code=400, detail="Bitbucket base URL not provided via query param or BITBUCKET_BASE_URL env var")

    proj = project or os.getenv("BITBUCKET_PROJECT") or ""
    if not proj:
        raise HTTPException(status_code=400, detail="Project key not provided via query param or BITBUCKET_PROJECT env var")

    api_url = f"{base}/rest/api/1.0/projects/{proj}/repos"

    token = os.getenv("BITBUCKET_TOKEN")
    if not token:
        raise HTTPException(status_code=500, detail="Missing BITBUCKET_TOKEN in environment/.env")

    repos: list[RepoResponse] = []
    start = 0

    while True:
        params = {"limit": limit, "start": start}

        resp = _get_with_token(api_url, token, params=params, verify_ssl=(not insecure))

        if resp is None:
            raise HTTPException(status_code=500, detail="No response received from Bitbucket")

        if resp.status_code in (401, 403):
            raise HTTPException(status_code=401, detail="Authentication failed (401/403)")

        if resp.status_code == 404:
            raise HTTPException(status_code=404, detail="Project not found (404)")

        try:
            resp.raise_for_status()
        except requests.HTTPError as e:
            raise HTTPException(status_code=resp.status_code, detail=f"Bitbucket error: {str(e)}")

        data: Dict[str, Any] = resp.json()

        for r in data.get("values", []):
            slug = r.get("slug") or r.get("name") or str(r.get("id", ""))
            repos.append(RepoResponse(
                id=slug,
                org_id=r.get("project", {}).get("key", proj),
                name=r.get("name") or slug,
                default_branch=(r.get("defaultBranch") or {}).get("displayId", "") or "main",
                connected=True,
            ))

        if data.get("isLastPage", True):
            break

        start = data.get("nextPageStart")
        if start is None:
            break

    return repos
