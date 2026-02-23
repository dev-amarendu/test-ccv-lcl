"""Firestore repository for schedules."""

from __future__ import annotations

from datetime import datetime, timezone

from google.cloud.firestore_v1 import AsyncClient

from shared.firestore_models import ScheduleDoc

COLLECTION = "schedules"


class ScheduleStore:
    """CRUD operations for the schedules collection."""

    def __init__(self, db: AsyncClient) -> None:
        self._col = db.collection(COLLECTION)

    async def create_schedule(self, schedule: ScheduleDoc) -> ScheduleDoc:
        await self._col.document(schedule.id).set(schedule.to_firestore_dict())
        return schedule

    async def get_schedule(self, schedule_id: str) -> ScheduleDoc | None:
        snap = await self._col.document(schedule_id).get()
        return ScheduleDoc.from_firestore_doc(snap.to_dict()) if snap.exists else None

    async def list_schedules(self, repo_id: str | None = None) -> list[ScheduleDoc]:
        query = self._col
        if repo_id:
            query = query.where("repo_id", "==", repo_id)
        docs = query.stream()
        return [ScheduleDoc.from_firestore_doc(d.to_dict()) async for d in docs]

    async def update_schedule(self, schedule_id: str, updates: dict) -> None:
        updates["updated_at"] = datetime.now(timezone.utc)
        await self._col.document(schedule_id).update(updates)

    async def delete_schedule(self, schedule_id: str) -> None:
        await self._col.document(schedule_id).delete()

    async def list_due_schedules(self, now: datetime | None = None) -> list[ScheduleDoc]:
        """Return enabled schedules whose next_run_at <= now."""
        if now is None:
            now = datetime.now(timezone.utc)
        query = (
            self._col.where("enabled", "==", True)
            .where("next_run_at", "<=", now)
        )
        docs = query.stream()
        return [ScheduleDoc.from_firestore_doc(d.to_dict()) async for d in docs]
