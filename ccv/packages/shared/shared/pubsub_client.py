"""Cloud Pub/Sub publisher helper for CCV job dispatch."""

from __future__ import annotations

import json
import logging
from typing import Any

from google.cloud import pubsub_v1

from shared.config import get_settings

logger = logging.getLogger(__name__)

_publisher: pubsub_v1.PublisherClient | None = None


def get_publisher() -> pubsub_v1.PublisherClient:
    """Return a cached Pub/Sub publisher client."""
    global _publisher
    if _publisher is None:
        _publisher = pubsub_v1.PublisherClient()
    return _publisher


def _topic_path(topic_name: str) -> str:
    settings = get_settings()
    project = settings.pubsub_project_id or settings.google_cloud_project
    return get_publisher().topic_path(project, topic_name)


def publish_message(topic_name: str, payload: dict[str, Any]) -> str:
    """Publish a JSON message to a Pub/Sub topic.

    Args:
        topic_name: short topic name, e.g. ``"ccv-analyze-finding"``
        payload: JSON-serializable dict

    Returns:
        Published message ID.
    """
    publisher = get_publisher()
    topic = _topic_path(topic_name)
    data = json.dumps(payload, default=str).encode("utf-8")
    future = publisher.publish(topic, data)
    message_id = future.result()
    logger.info("Published message %s to %s", message_id, topic_name)
    return message_id


# ── Convenience functions per job type ──────────────────────────────────────


def publish_analyze_finding(finding_id: str) -> str:
    settings = get_settings()
    return publish_message(
        settings.pubsub_topic_analyze_finding,
        {"finding_id": finding_id},
    )


def publish_run_scan(scan_id: str) -> str:
    settings = get_settings()
    return publish_message(
        settings.pubsub_topic_run_scan,
        {"scan_id": scan_id},
    )


def publish_sync_veracode() -> str:
    settings = get_settings()
    return publish_message(
        settings.pubsub_topic_sync_veracode,
        {"action": "sync"},
    )


def publish_embed_kb(card_id: str) -> str:
    settings = get_settings()
    return publish_message(
        settings.pubsub_topic_embed_kb,
        {"card_id": card_id},
    )
