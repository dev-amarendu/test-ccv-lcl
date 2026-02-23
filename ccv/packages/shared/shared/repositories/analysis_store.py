"""Firestore repository for finding analyses."""

from __future__ import annotations

from datetime import datetime, timezone

from google.cloud.firestore_v1 import AsyncClient

from shared.firestore_models import FindingAnalysisDoc

COLLECTION = "finding_analyses"


class AnalysisStore:
    """CRUD operations for the finding_analyses collection."""

    def __init__(self, db: AsyncClient) -> None:
        self._col = db.collection(COLLECTION)

    async def create_analysis(self, analysis: FindingAnalysisDoc) -> FindingAnalysisDoc:
        await self._col.document(analysis.id).set(analysis.to_firestore_dict())
        return analysis

    async def get_analysis(self, analysis_id: str) -> FindingAnalysisDoc | None:
        snap = await self._col.document(analysis_id).get()
        return FindingAnalysisDoc.from_firestore_doc(snap.to_dict()) if snap.exists else None

    async def get_by_finding_id(self, finding_id: str) -> FindingAnalysisDoc | None:
        query = self._col.where("finding_id", "==", finding_id).limit(1)
        async for doc in query.stream():
            return FindingAnalysisDoc.from_firestore_doc(doc.to_dict())
        return None

    async def update_analysis(self, analysis_id: str, updates: dict) -> None:
        updates["updated_at"] = datetime.now(timezone.utc)
        await self._col.document(analysis_id).update(updates)
