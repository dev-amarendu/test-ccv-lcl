"""Helper to get/update veracode_sync_state from Firestore.

Uses the SyncStateStore repository for the singleton document pattern.
"""

from __future__ import annotations

from datetime import datetime

from shared.firestore_client import get_firestore_client
from shared.firestore_models import VeracodeSyncStateDoc
from shared.logging import get_logger
from shared.repositories.sync_state_store import SyncStateStore

logger = get_logger(__name__)


async def get_sync_state() -> VeracodeSyncStateDoc:
    """Retrieve the current sync state, creating the singleton doc if needed."""
    client = get_firestore_client()
    store = SyncStateStore(client)
    state = await store.get_state()

    if state is None:
        state = VeracodeSyncStateDoc(
            last_synced_at=None,
            last_seen_build_id=None,
        )
        await store.update_state(state)

    logger.info(
        "veracode_sync_state_read",
        last_synced_at=str(state.last_synced_at),
        last_seen_build_id=state.last_seen_build_id,
    )
    return state


async def update_sync_state(
    last_synced_at: datetime,
    last_seen_build_id: str | None = None,
) -> None:
    """Atomically update the sync state high-water mark."""
    client = get_firestore_client()
    store = SyncStateStore(client)

    state = VeracodeSyncStateDoc(
        last_synced_at=last_synced_at,
        last_seen_build_id=last_seen_build_id,
    )
    await store.update_state(state)

    logger.info(
        "veracode_sync_state_updated",
        last_synced_at=str(last_synced_at),
        last_seen_build_id=last_seen_build_id,
    )
