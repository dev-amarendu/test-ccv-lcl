"""Firestore repository for repos (code repositories)."""

from __future__ import annotations

from google.cloud.firestore_v1 import AsyncClient

from shared.firestore_models import RepoDoc

COLLECTION = "repos"


class RepoStore:
    """CRUD operations for the repos collection."""

    def __init__(self, db: AsyncClient) -> None:
        self._col = db.collection(COLLECTION)

    async def list_repos(self, org_id: str | None = None) -> list[RepoDoc]:
        query = self._col
        if org_id:
            query = query.where("org_id", "==", org_id)
        docs = query.stream()
        return [RepoDoc.from_firestore_doc(d.to_dict()) async for d in docs]

    async def get_repo(self, repo_id: str) -> RepoDoc | None:
        snap = await self._col.document(repo_id).get()
        return RepoDoc.from_firestore_doc(snap.to_dict()) if snap.exists else None

    async def create_repo(self, repo: RepoDoc) -> RepoDoc:
        await self._col.document(repo.id).set(repo.to_firestore_dict())
        return repo

    async def update_repo(self, repo_id: str, updates: dict) -> None:
        await self._col.document(repo_id).update(updates)

    async def get_connected_repo(self) -> RepoDoc | None:
        """Get the first repo marked as connected."""
        query = self._col.where("connected", "==", True).limit(1)
        async for doc in query.stream():
            return RepoDoc.from_firestore_doc(doc.to_dict())
        return None
