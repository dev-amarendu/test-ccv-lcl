import sys
import os

# Add packages to path
sys.path.append(os.path.abspath("./packages/shared"))
sys.path.append(os.path.abspath("./packages/api_service"))

import asyncio
from google.cloud import firestore

async def debug():
    # Use the async client as the codebase does
    db = firestore.AsyncClient(project="test-ccv-lcl", database="(default)")
    
    col = db.collection("scans")
    snap = await col.document("81a4693b-f5fc-4170-a48c-af64deb38dc2").get()
    
    if not snap.exists:
        print("Document does not exist!")
        return
        
    data = snap.to_dict()
    print("RAW DATA:")
    print(data)
    
    try:
        from shared.firestore_models import ScanDoc
        doc = ScanDoc.from_firestore_doc(data)
        print("PARSED OK:")
        print(doc)
    except Exception as e:
        import traceback
        print("PYDANTIC ERROR:")
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(debug())
