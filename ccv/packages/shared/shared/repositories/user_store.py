"""Firestore repository for users."""

from __future__ import annotations

from google.cloud.firestore_v1 import AsyncClient

from shared.firestore_models import UserDoc

COLLECTION = "users"


class UserStore:
    """CRUD operations for the users collection."""

    def __init__(self, db: AsyncClient) -> None:
        self._col = db.collection(COLLECTION)

    async def get_user(self, user_id: str) -> UserDoc | None:
        snap = await self._col.document(user_id).get()
        return UserDoc.from_firestore_doc(snap.to_dict()) if snap.exists else None

    async def get_by_email(self, email: str) -> UserDoc | None:
        query = self._col.where("email", "==", email).limit(1)
        async for doc in query.stream():
            return UserDoc.from_firestore_doc(doc.to_dict())
        return None

    async def create_user(self, user: UserDoc) -> UserDoc:
        await self._col.document(user.id).set(user.to_firestore_dict())
        return user

    async def update_user(self, user_id: str, updates: dict) -> None:
        await self._col.document(user_id).update(updates)
