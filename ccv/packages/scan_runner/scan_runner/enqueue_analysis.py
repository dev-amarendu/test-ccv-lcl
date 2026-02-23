"""Enqueue ANALYZE_FINDING messages via Pub/Sub for each finding in a scan."""

from __future__ import annotations

from shared.firestore_models import FindingDoc
from shared.logging import get_logger
from shared.pubsub_client import publish_analyze_finding

logger = get_logger(__name__)


async def enqueue_analysis_jobs(scan_id: str, findings: list[FindingDoc]) -> int:
    """Publish ANALYZE_FINDING messages to Pub/Sub for each finding.

    Returns the number of messages published.
    """
    for finding in findings:
        publish_analyze_finding(finding.id)

    logger.info("analysis_jobs_enqueued", scan_id=scan_id, count=len(findings))
    return len(findings)
