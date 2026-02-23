"""Firestore repository for scans + scan_artifacts subcollection."""

from __future__ import annotations

from datetime import datetime, timezone

from google.cloud.firestore_v1 import AsyncClient

from shared.firestore_models import ScanArtifactDoc, ScanDoc, ScanStatus

COLLECTION = "scans"


class ScanStore:
    """CRUD operations for the scans collection."""

    def __init__(self, db: AsyncClient) -> None:
        self._db = db
        self._col = db.collection(COLLECTION)

    # ── Create / Read ────────────────────────────────────────────────────

    async def create_scan(self, scan: ScanDoc) -> ScanDoc:
        await self._col.document(scan.id).set(scan.to_firestore_dict())
        return scan

    async def get_scan(self, scan_id: str) -> ScanDoc | None:
        snap = await self._col.document(scan_id).get()
        return ScanDoc.from_firestore_doc(snap.to_dict()) if snap.exists else None

    async def list_scans(
        self,
        repo_id: str | None = None,
        status: ScanStatus | None = None,
        page: int = 1,
        page_size: int = 50,
    ) -> tuple[list[ScanDoc], int]:
        query = self._col
        if repo_id:
            query = query.where("repo_id", "==", repo_id)
        if status:
            query = query.where("status", "==", status.value)
        query = query.order_by("created_at", direction="DESCENDING")

        # Count total (Firestore aggregation)
        count_query = query.count()
        count_result = await count_query.get()
        total = count_result[0][0].value if count_result and count_result[0] else 0

        # Paginate
        offset = (max(1, page) - 1) * page_size
        query = query.offset(offset).limit(page_size)
        docs = query.stream()
        items = [ScanDoc.from_firestore_doc(d.to_dict()) async for d in docs]
        return items, total

    # ── Update ───────────────────────────────────────────────────────────

    async def update_scan(self, scan_id: str, updates: dict) -> None:
        updates["updated_at"] = datetime.now(timezone.utc)
        await self._col.document(scan_id).update(updates)

    # ── Lookup ───────────────────────────────────────────────────────────

    async def find_by_external_build_id(self, build_id: str) -> ScanDoc | None:
        query = self._col.where("external_build_id", "==", build_id).limit(1)
        async for doc in query.stream():
            return ScanDoc.from_firestore_doc(doc.to_dict())
        return None

    # ── Artifacts (subcollection) ─────────────────────────────────────

    async def add_artifact(self, scan_id: str, artifact: ScanArtifactDoc) -> ScanArtifactDoc:
        sub_col = self._col.document(scan_id).collection("artifacts")
        await sub_col.document(artifact.id).set(artifact.to_firestore_dict())
        return artifact

    async def list_artifacts(self, scan_id: str) -> list[ScanArtifactDoc]:
        sub_col = self._col.document(scan_id).collection("artifacts")
        docs = sub_col.stream()
        return [ScanArtifactDoc.from_firestore_doc(d.to_dict()) async for d in docs]
