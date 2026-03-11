"""Pub/Sub push subscription handler endpoints.

These endpoints receive push messages from Cloud Pub/Sub subscriptions.
Each endpoint decodes the Pub/Sub envelope, extracts the payload, and
dispatches the work to the appropriate handler function.
"""

from __future__ import annotations

import base64
import json

from fastapi import APIRouter, Request

from shared.logging import get_logger

router = APIRouter(tags=["pubsub-tasks"])
logger = get_logger(__name__)


def _decode_pubsub_message(request_body: dict) -> dict:
    """Decode the data from a Pub/Sub push message envelope."""
    message = request_body.get("message", {})
    data_b64 = message.get("data", "")
    if not data_b64:
        return {}
    decoded = base64.b64decode(data_b64).decode("utf-8")
    return json.loads(decoded)


# ── POST /pubsub/analyze-finding ─────────────────────────────────────────────


@router.post("/analyze-finding")
async def handle_analyze_finding(request: Request) -> dict:
    """Receive a Pub/Sub push for ANALYZE_FINDING.

    This endpoint is called by the Pub/Sub push subscription.
    Returning 2xx acknowledges the message; non-2xx triggers retry.
    """
    body = await request.json()
    payload = _decode_pubsub_message(body)
    finding_id = payload.get("finding_id")

    if not finding_id:
        logger.warning("analyze_finding_missing_id", body=body)
        return {"status": "skipped", "reason": "missing finding_id"}

    logger.info("analyze_finding_received", finding_id=finding_id)

    # Import here to avoid circular deps — the analysis logic lives in analysis_agent
    try:
        from analysis_agent.agent import analyze_finding
        await analyze_finding(finding_id)
    except ImportError:
        logger.warning("analysis_agent_not_available")
    except Exception as exc:
        logger.error("analyze_finding_error", finding_id=finding_id, error=str(exc))
        raise  # Return 500 → Pub/Sub will retry

    return {"status": "ok", "finding_id": finding_id}


# ── POST /pubsub/run-scan ────────────────────────────────────────────────────


@router.post("/run-scan")
async def handle_run_scan(request: Request) -> dict:
    """Receive a Pub/Sub push for RUN_SCAN."""
    body = await request.json()
    payload = _decode_pubsub_message(body)
    scan_id = payload.get("scan_id")

    if not scan_id:
        logger.warning("run_scan_missing_id", body=body)
        return {"status": "skipped", "reason": "missing scan_id"}

    logger.info("run_scan_received", scan_id=scan_id)

    try:
        from scan_runner.orchestrator import run_scan_pipeline
        await run_scan_pipeline(scan_id)
    except ImportError:
        logger.warning("scan_runner_not_available")
    except InterruptedError:
        logger.warning("run_scan_cancelled", scan_id=scan_id)
        return {"status": "cancelled", "scan_id": scan_id}
    except Exception as exc:
        logger.error("run_scan_error", scan_id=scan_id, error=str(exc))
        raise

    return {"status": "ok", "scan_id": scan_id}


# ── POST /pubsub/sync-veracode ───────────────────────────────────────────────


@router.post("/sync-veracode")
async def handle_sync_veracode(request: Request) -> dict:
    """Receive a Pub/Sub push for SYNC_VERACODE (triggered by Cloud Scheduler)."""
    body = await request.json()
    _decode_pubsub_message(body)  # validate envelope

    logger.info("sync_veracode_received")

    try:
        from scan_runner.poller import run_sync_once
        await run_sync_once()
    except ImportError:
        logger.warning("scan_runner_not_available")
    except Exception as exc:
        logger.error("sync_veracode_error", error=str(exc))
        raise

    return {"status": "ok"}


# ── POST /pubsub/embed-kb ────────────────────────────────────────────────────


@router.post("/embed-kb")
async def handle_embed_kb(request: Request) -> dict:
    """Receive a Pub/Sub push for EMBED_KB."""
    body = await request.json()
    payload = _decode_pubsub_message(body)
    card_id = payload.get("card_id")

    if not card_id:
        logger.warning("embed_kb_missing_id", body=body)
        return {"status": "skipped", "reason": "missing card_id"}

    logger.info("embed_kb_received", card_id=card_id)

    try:
        from kb_service.store import embed_and_upsert_card
        await embed_and_upsert_card(card_id)
    except ImportError:
        logger.warning("kb_service_not_available")
    except Exception as exc:
        logger.error("embed_kb_error", card_id=card_id, error=str(exc))
        raise

    return {"status": "ok", "card_id": card_id}
