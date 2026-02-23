"""Scan artifact listing endpoint."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from google.cloud.firestore_v1 import AsyncClient

from shared.logging import get_logger
from shared.repositories.scan_store import ScanStore
from shared.schemas import ArtifactResponse

from api_service.deps import db_session

router = APIRouter(prefix="/artifacts", tags=["artifacts"])
logger = get_logger(__name__)


@router.get("", response_model=list[ArtifactResponse])
async def list_artifacts(
    repo_id: str = Query(..., alias="repoId", description="Filter by repo"),
    branch: str = Query(..., description="Filter by branch"),
    db: AsyncClient = Depends(db_session),
) -> list[ArtifactResponse]:
    """List scan artifacts for a given repo and branch.

    Queries scans matching repo_id and branch, then fetches their artifacts
    from the subcollection.
    """
    store = ScanStore(db)
    # Get scans for the repo (all statuses)
    scans_col = db.collection("scans")
    query = scans_col.where("repo_id", "==", repo_id).where("branch", "==", branch)
    scan_docs = query.stream()

    artifacts = []
    async for scan_doc in scan_docs:
        scan_artifacts = await store.list_artifacts(scan_doc.id)
        for a in scan_artifacts:
            artifacts.append(
                ArtifactResponse(
                    id=a.id, scan_id=a.scan_id,
                    artifact_uri=a.artifact_uri,
                    artifact_sha256=a.artifact_sha256,
                    build_tool=a.build_tool,
                    created_at=a.created_at,
                )
            )

    logger.debug(
        "artifacts_listed",
        repo_id=repo_id,
        branch=branch,
        count=len(artifacts),
    )
    return artifacts
