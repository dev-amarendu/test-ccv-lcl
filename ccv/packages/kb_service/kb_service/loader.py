"""Load CWE-660 CSV into Firestore and generate embeddings.

Usage:
    python -m kb_service.loader --csv-path /path/to/cwe-660.csv
    python -m kb_service.loader --embed-only
"""

from __future__ import annotations

import argparse
import asyncio
import csv
from pathlib import Path

from shared.config import get_settings
from shared.firestore_client import get_firestore_client
from shared.firestore_models import KBFixCardDoc
from shared.logging import get_logger, setup_logging
from shared.repositories.kb_store import KBFixCardStore

from kb_service.embeddings import embed_text
from kb_service.store import upsert_fix_card
from kb_service.templates import generate_fix_card_content

logger = get_logger(__name__)


def _read_cwe_csv(csv_path: str) -> list[dict]:
    """Read a CWE CSV file and return list of dicts."""
    path = Path(csv_path)
    if not path.exists():
        raise FileNotFoundError(f"CWE CSV not found: {csv_path}")

    records = []
    with open(path, "r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            normalized = {}
            for k, v in row.items():
                key = k.strip().lower().replace(" ", "_").replace("-", "_")
                normalized[key] = (v or "").strip()
            records.append(normalized)

    logger.info("cwe_csv_loaded", path=csv_path, records=len(records))
    return records


async def load_cwe_csv(csv_path: str, generate_embeddings: bool = True) -> int:
    """Load CWE-660 CSV into Firestore kb_fix_cards collection."""
    records = _read_cwe_csv(csv_path)
    count = 0

    for rec in records:
        cwe_id_raw = rec.get("cwe_id", rec.get("cwe-id", rec.get("id", "")))
        if not cwe_id_raw:
            continue

        cwe_id_str = str(cwe_id_raw).replace("CWE-", "").strip()
        if not cwe_id_str.isdigit():
            continue

        cwe_id = int(cwe_id_str)
        name = rec.get("name", rec.get("title", f"CWE-{cwe_id}"))
        description = rec.get("description", "")
        extended = rec.get("extended_description", "")
        mitigations = rec.get("potential_mitigations", "")

        content = generate_fix_card_content(
            cwe_id=cwe_id,
            cwe_name=name,
            description=description,
            extended_description=extended,
            potential_mitigations=mitigations,
        )

        embedding = None
        if generate_embeddings:
            try:
                embedding = embed_text(content)
            except Exception as exc:
                logger.warning("embedding_failed", cwe_id=cwe_id, error=str(exc))

        tags = ["java", "cwe-660", f"cwe-{cwe_id}"]

        await upsert_fix_card(
            cwe_id=cwe_id,
            title=name,
            content=content,
            tags=tags,
            source="CWE-660",
            embedding=embedding,
        )
        count += 1
        if count % 50 == 0:
            logger.info("cwe_loading_progress", loaded=count, total=len(records))

    logger.info("cwe_loading_complete", total=count)
    return count


async def embed_existing_cards() -> int:
    """Re-embed all existing Fix Cards that have no embedding."""
    db = get_firestore_client()
    store = KBFixCardStore(db)
    settings = get_settings()

    # In Firestore, we have to iterate all or use a query. 
    # Store.list_cards is paginated, but here we likely want to scan all.
    # For simplicity, we'll fetch in batches if store supports it, or just use list_cards loop.
    
    # Creating a direct query here for "embedding == None" might be tricky if field is missing.
    # We'll just iterate all for migration scripts.
    
    count = 0
    page = 1
    while True:
        cards, total = await store.list_cards(page=page, page_size=100)
        if not cards:
            break
            
        for card in cards:
            if not card.embedding:
                try:
                    embedding = embed_text(card.content)
                    await store.update_card(card.id, {
                        "embedding": embedding,
                        "embedding_model": settings.embedding_model,
                        "embedding_dim": len(embedding),
                    })
                    count += 1
                except Exception as exc:
                    logger.warning("re_embedding_failed", cwe_id=card.cwe_id, error=str(exc))
        
        page += 1

    logger.info("re_embedding_complete", count=count)
    return count


def main() -> None:
    setup_logging(get_settings().api_log_level)

    parser = argparse.ArgumentParser(description="CCV KB Loader")
    parser.add_argument("--csv-path", type=str, help="Path to CWE-660 CSV file")
    parser.add_argument("--no-embed", action="store_true", help="Skip embedding generation")
    parser.add_argument("--embed-only", action="store_true", help="Re-embed existing cards without embedding")
    args = parser.parse_args()

    if args.embed_only:
        asyncio.run(embed_existing_cards())
    elif args.csv_path:
        asyncio.run(load_cwe_csv(args.csv_path, generate_embeddings=not args.no_embed))
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
