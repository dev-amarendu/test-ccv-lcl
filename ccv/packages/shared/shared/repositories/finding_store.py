"""Firestore repository for findings."""

from __future__ import annotations

from google.cloud.firestore_v1 import AsyncClient

from shared.firestore_models import FindingDoc

COLLECTION = "findings"


class FindingStore:
    """CRUD operations for the findings collection."""

    def __init__(self, db: AsyncClient) -> None:
        self._db = db
        self._col = db.collection(COLLECTION)

    async def create_finding(self, finding: FindingDoc) -> FindingDoc:
        await self._col.document(finding.id).set(finding.to_firestore_dict())
        return finding

    async def create_findings(self, findings: list[FindingDoc]) -> list[FindingDoc]:
        """Batch-write multiple findings (up to 500 per batch)."""
        batch = self._db.batch()
        for f in findings:
            ref = self._col.document(f.id)
            batch.set(ref, f.to_firestore_dict())
        await batch.commit()
        return findings

    async def get_finding(self, finding_id: str) -> FindingDoc | None:
        snap = await self._col.document(finding_id).get()
        return FindingDoc.from_firestore_doc(snap.to_dict()) if snap.exists else None

    async def list_findings(
        self,
        scan_id: str | None = None,
        cwe_id: int | None = None,
        severity: str | None = None,
        page: int = 1,
        page_size: int = 50,
    ) -> tuple[list[FindingDoc], int]:
        query = self._col
        if scan_id:
            query = query.where("scan_id", "==", scan_id)
        if cwe_id is not None:
            query = query.where("cwe_id", "==", cwe_id)
        if severity:
            query = query.where("severity", "==", severity)
        
        mapped_filters = any([scan_id, cwe_id is not None, severity])
        if not mapped_filters:
            query = query.order_by("created_at", direction="DESCENDING")

        # Count
        count_query = query.count()
        count_result = await count_query.get()
        total = count_result[0][0].value if count_result and count_result[0] else 0

        # Paginate
        offset = (max(1, page) - 1) * page_size
        query = query.offset(offset).limit(page_size)
        docs = query.stream()
        items = [FindingDoc.from_firestore_doc(d.to_dict()) async for d in docs]
        return items, total

    async def find_by_fingerprint(self, fingerprint: str, scan_id: str) -> FindingDoc | None:
        query = (
            self._col.where("fingerprint", "==", fingerprint)
            .where("scan_id", "==", scan_id)
            .limit(1)
        )
        async for doc in query.stream():
            return FindingDoc.from_firestore_doc(doc.to_dict())
        return None
