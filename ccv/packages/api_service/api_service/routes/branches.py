"""Branch listing endpoint — fetches directly from Bitbucket Server/DC.

Endpoints:
- GET /branches?repoId=...  -> lists branches for a repository
"""

from __future__ import annotations

import os
from typing import Optional, Dict, Any, List

import requests
from fastapi import APIRouter, HTTPException, Query
from dotenv import load_dotenv

from shared.logging import get_logger
from shared.schemas import BranchResponse

load_dotenv()

router = APIRouter(prefix="/branches", tags=["branches"])
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
    """Try Bearer first, then Token."""
    last_resp = None
    for scheme in ("Bearer", "Token"):
        headers = _make_headers(token, scheme)
        resp = requests.get(
            url, headers=headers, params=params,
            timeout=30, verify=verify_ssl,
        )
        last_resp = resp
        if resp.status_code in (401, 403):
            continue
        return resp
    return last_resp


@router.get("", response_model=list[BranchResponse])
def list_branches(
    repo_id: str = Query(..., alias="repoId", description="Repository slug"),
    base_url: Optional[str] = Query(None, description="Bitbucket base URL"),
    project: Optional[str] = Query(None, description="Project key"),
    limit: int = Query(100, ge=1, le=1000),
    insecure: bool = Query(False, description="Set true to disable SSL verification"),
) -> list[BranchResponse]:
    """
    Lists branches for a repository from Bitbucket Server/DC.
    Returns Branch objects with name and is_default flag.
    """
    base = (base_url or os.getenv("BITBUCKET_BASE_URL") or "").rstrip("/")
    if not base:
        raise HTTPException(status_code=400, detail="Bitbucket base URL not provided via query param or BITBUCKET_BASE_URL env var")

    proj = project or os.getenv("BITBUCKET_PROJECT") or ""
    if not proj:
        raise HTTPException(status_code=400, detail="Project key not provided via query param or BITBUCKET_PROJECT env var")

    token = os.getenv("BITBUCKET_TOKEN")
    if not token:
        raise HTTPException(status_code=500, detail="Missing BITBUCKET_TOKEN in environment/.env")

    api_url = f"{base}/rest/api/1.0/projects/{proj}/repos/{repo_id}/branches"
    verify = not insecure

    branches: list[BranchResponse] = []
    start = 0

    while True:
        params = {"limit": limit, "start": start}
        resp = _get_with_token(api_url, token, params=params, verify_ssl=verify)

        if resp is None:
            raise HTTPException(status_code=500, detail="No response received from Bitbucket")

        if resp.status_code in (401, 403):
            raise HTTPException(status_code=401, detail="Authentication failed (401/403)")

        if resp.status_code == 404:
            raise HTTPException(status_code=404, detail="Repository not found (404)")

        try:
            resp.raise_for_status()
        except requests.HTTPError as e:
            raise HTTPException(status_code=resp.status_code, detail=f"Bitbucket error: {str(e)}")

        data: Dict[str, Any] = resp.json()

        for b in data.get("values", []):
            branches.append(BranchResponse(
                name=b.get("displayId") or b.get("id", ""),
                is_default=b.get("isDefault", False),
            ))

        if data.get("isLastPage", True):
            break

        start = data.get("nextPageStart")
        if start is None:
            break

    logger.debug("branches_listed", repo_id=repo_id, count=len(branches))
    return branches
