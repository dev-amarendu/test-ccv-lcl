"""Firestore repository for audit logs."""

from __future__ import annotations

from google.cloud.firestore_v1 import AsyncClient

from shared.firestore_models import AuditLogDoc

COLLECTION = "audit_logs"


class AuditStore:
    """Append-only audit log store."""

    def __init__(self, db: AsyncClient) -> None:
        self._col = db.collection(COLLECTION)

    async def log_entry(self, entry: AuditLogDoc) -> AuditLogDoc:
        await self._col.document(entry.id).set(entry.to_firestore_dict())
        return entry

    async def list_logs(
        self, page: int = 1, page_size: int = 50
    ) -> tuple[list[AuditLogDoc], int]:
        query = self._col.order_by("created_at", direction="DESCENDING")

        count_query = query.count()
        count_result = await count_query.get()
        total = count_result[0][0].value if count_result and count_result[0] else 0

        offset = (max(1, page) - 1) * page_size
        query = query.offset(offset).limit(page_size)
        docs = query.stream()
        items = [AuditLogDoc.from_firestore_doc(d.to_dict()) async for d in docs]
        return items, total
