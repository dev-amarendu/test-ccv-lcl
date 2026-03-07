from __future__ import annotations
import asyncio
import os
import sys

from dotenv import load_dotenv
load_dotenv("../../.env")

from shared.firestore_client import get_firestore_client

async def clear_all():
    db = get_firestore_client()
    collections = ['findings', 'scans', 'scan_artifacts', 'finding_analyses', 'audit_log', 'schedules']
    print(f"Connecting to {db.project} / {db._database}")
    
    for coll in collections:
        print(f"Wiping collection: {coll}...")
        docs = db.collection(coll).stream()
        batch = db.batch()
        count = 0
        total = 0
        async for doc in docs:
            batch.delete(doc.reference)
            count += 1
            total += 1
            if count >= 450:
                await batch.commit()
                batch = db.batch()
                count = 0
        if count > 0:
            await batch.commit()
        print(f"Deleted {total} from {coll}")
    print("DONE wiping database.")

if __name__ == "__main__":
    asyncio.run(clear_all())
