"""Firestore repository for KB fix cards."""

from __future__ import annotations

from datetime import datetime, timezone

from google.cloud.firestore_v1 import AsyncClient
from google.cloud.firestore_v1 import transforms

from shared.firestore_models import KBFixCardDoc

COLLECTION = "kb_fix_cards"


class KBFixCardStore:
    """CRUD operations for the kb_fix_cards collection."""

    def __init__(self, db: AsyncClient) -> None:
        self._col = db.collection(COLLECTION)

    async def get_by_cwe(self, cwe_id: int) -> KBFixCardDoc | None:
        query = self._col.where("cwe_id", "==", cwe_id).limit(1)
        async for doc in query.stream():
            return KBFixCardDoc.from_firestore_doc(doc.to_dict())
        return None

    async def get_by_id(self, card_id: str) -> KBFixCardDoc | None:
        snap = await self._col.document(card_id).get()
        return KBFixCardDoc.from_firestore_doc(snap.to_dict()) if snap.exists else None

    async def list_cards(self, page: int = 1, page_size: int = 50) -> tuple[list[KBFixCardDoc], int]:
        query = self._col.order_by("cwe_id")

        count_query = query.count()
        count_result = await count_query.get()
        total = count_result[0][0].value if count_result and count_result[0] else 0

        offset = (max(1, page) - 1) * page_size
        query = query.offset(offset).limit(page_size)
        docs = query.stream()
        items = [KBFixCardDoc.from_firestore_doc(d.to_dict()) async for d in docs]
        return items, total

    async def upsert(self, card: KBFixCardDoc) -> KBFixCardDoc:
        await self._col.document(card.id).set(card.to_firestore_dict(), merge=True)
        return card

    async def update_card(self, card_id: str, updates: dict) -> None:
        updates["updated_at"] = datetime.now(timezone.utc)
        await self._col.document(card_id).update(updates)

    async def increment_usage(self, card_id: str) -> None:
        await self._col.document(card_id).update({
            "usage_count": transforms.Increment(1),
            "updated_at": datetime.now(timezone.utc),
        })
