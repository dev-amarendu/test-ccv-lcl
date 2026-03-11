"""CLI entry point for the scan runner.

Usage:
    python -m scan_runner.runner --scan-id <uuid>

In production, scans are triggered by Pub/Sub push messages to the
/pubsub/run-scan endpoint. This CLI is kept for manual debugging.
"""

from __future__ import annotations

import argparse
import asyncio
import sys
import uuid
from datetime import datetime, timezone

from shared.config import get_settings
from shared.firestore_client import get_firestore_client
from shared.firestore_models import ScanStatus
from shared.logging import get_logger, set_request_id, setup_logging
from shared.repositories.scan_store import ScanStore

from scan_runner.orchestrator import run_scan_pipeline

logger = get_logger(__name__)


async def execute_scan(scan_id: str) -> None:
    """Run the full scan pipeline for a given scan_id."""
    rid = uuid.uuid4().hex[:16]
    set_request_id(rid)
    logger.info("scan_runner_start", scan_id=scan_id)

    db = get_firestore_client()
    scan_store = ScanStore(db)

    scan = await scan_store.get_scan(scan_id)
    if not scan:
        logger.error("scan_not_found", scan_id=scan_id)
        return

    # Mark scan as RUNNING
    await scan_store.update_scan(scan_id, {
        "status": ScanStatus.RUNNING.value,
        "started_at": datetime.now(timezone.utc),
    })

    try:
        await run_scan_pipeline(scan_id)

        # Mark COMPLETED
        await scan_store.update_scan(scan_id, {
            "status": ScanStatus.COMPLETED.value,
            "finished_at": datetime.now(timezone.utc),
        })
        logger.info("scan_runner_completed", scan_id=scan_id)

    except InterruptedError:
        logger.info("scan_runner_cancelled", scan_id=scan_id)
        # Scan was manually cancelled. We don't overwrite the CANCELLED status.

    except Exception as exc:
        import traceback
        tb_str = traceback.format_exc()
        logger.error("scan_runner_failed", scan_id=scan_id, error=str(exc), traceback=tb_str)
        await scan_store.update_scan(scan_id, {
            "status": ScanStatus.FAILED.value,
            "error_message": f"{str(exc)[:1500]}\n\nTraceback:\n{tb_str[:500]}",
        })


def main() -> None:
    setup_logging(get_settings().api_log_level)

    parser = argparse.ArgumentParser(description="CCV Scan Runner")
    parser.add_argument("--scan-id", type=str, help="Run a specific scan by ID")
    args = parser.parse_args()

    if args.scan_id:
        asyncio.run(execute_scan(args.scan_id))
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
