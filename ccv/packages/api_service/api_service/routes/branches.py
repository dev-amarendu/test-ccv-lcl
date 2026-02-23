"""Branch listing endpoint (mock mode — returns common branch names)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from google.cloud.firestore_v1 import AsyncClient

from shared.logging import get_logger
from shared.repositories.repos import RepoStore
from shared.schemas import BranchResponse

from api_service.deps import db_session

router = APIRouter(prefix="/branches", tags=["branches"])
logger = get_logger(__name__)

# Common branch names returned in mock mode alongside the repo's default_branch
_MOCK_EXTRA_BRANCHES = [
    "develop",
    "staging",
    "release/1.0",
    "feature/security-scan",
]


@router.get("", response_model=list[BranchResponse])
async def list_branches(
    repo_id: str = Query(..., alias="repoId", description="Repo UUID"),
    db: AsyncClient = Depends(db_session),
) -> list[BranchResponse]:
    """Return branches for a repo.

    In production this would call Bitbucket / Git provider APIs.
    For now it returns the repo's ``default_branch`` plus common mock names.
    """
    store = RepoStore(db)
    repo = await store.get_repo(repo_id)
    if not repo:
        raise HTTPException(status_code=404, detail="Repo not found")

    branches: list[BranchResponse] = [
        BranchResponse(name=repo.default_branch, is_default=True),
    ]

    for name in _MOCK_EXTRA_BRANCHES:
        if name != repo.default_branch:
            branches.append(BranchResponse(name=name, is_default=False))

    logger.debug("branches_listed", repo_id=repo_id, count=len(branches))
    return branches
