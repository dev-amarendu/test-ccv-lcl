import asyncio
import sys
import os

sys.path.append(os.path.join(os.getcwd(), "packages", "shared"))
sys.path.append(os.path.join(os.getcwd(), "packages", "api_service"))

from shared.firestore_client import get_firestore_client
from shared.repositories.kb_store import KBFixCardStore

async def check():
    db = get_firestore_client()
    store = KBFixCardStore(db)
    items, total = await store.list_cards(page_size=100)
    print(f"Total reported by count(): {total}")
    print(f"Total returned by stream(): {len(items)}")
    for i in items:
        print(f"ID: {i.id} | CWE: {i.cwe_id} | Title: {i.title}")

if __name__ == "__main__":
    asyncio.run(check())
