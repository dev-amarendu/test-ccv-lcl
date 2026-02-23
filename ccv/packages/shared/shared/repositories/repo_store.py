"""Firestore repository for organizations."""

from __future__ import annotations

from google.cloud.firestore_v1 import AsyncClient

from shared.firestore_models import OrganizationDoc

COLLECTION = "organizations"


class RepoStoreOrg:
    """CRUD operations for the organizations collection."""

    def __init__(self, db: AsyncClient) -> None:
        self._col = db.collection(COLLECTION)

    async def list_orgs(self) -> list[OrganizationDoc]:
        docs = self._col.stream()
        return [OrganizationDoc.from_firestore_doc(d.to_dict()) async for d in docs]

    async def get_org(self, org_id: str) -> OrganizationDoc | None:
        snap = await self._col.document(org_id).get()
        return OrganizationDoc.from_firestore_doc(snap.to_dict()) if snap.exists else None

    async def create_org(self, org: OrganizationDoc) -> OrganizationDoc:
        await self._col.document(org.id).set(org.to_firestore_dict())
        return org

    async def delete_org(self, org_id: str) -> None:
        await self._col.document(org_id).delete()
