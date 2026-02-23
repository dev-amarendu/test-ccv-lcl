"""Firestore repository for Veracode sync state (singleton document)."""

from __future__ import annotations

from datetime import datetime

from google.cloud.firestore_v1 import AsyncClient

from shared.firestore_models import VeracodeSyncStateDoc

COLLECTION = "sync_state"
DOCUMENT_ID = "veracode"


class SyncStateStore:
    """Read/write the Veracode sync state singleton document."""

    def __init__(self, db: AsyncClient) -> None:
        self._ref = db.collection(COLLECTION).document(DOCUMENT_ID)

    async def get_state(self) -> VeracodeSyncStateDoc:
        snap = await self._ref.get()
        if snap.exists:
            return VeracodeSyncStateDoc.from_firestore_doc(snap.to_dict())
        # Bootstrap empty state
        state = VeracodeSyncStateDoc()
        await self._ref.set(state.to_firestore_dict())
        return state

    async def update_state(
        self,
        last_synced_at: datetime,
        last_seen_build_id: str | None = None,
    ) -> None:
        updates: dict = {"last_synced_at": last_synced_at}
        if last_seen_build_id is not None:
            updates["last_seen_build_id"] = last_seen_build_id
        await self._ref.set(updates, merge=True)
