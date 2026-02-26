"""Pub/Sub pull subscriber for the ccv-run-scan topic.

Usage (Terminal 3 — replaces the poller for manual/scheduled scans):
    python -m scan_runner.subscriber

Listens on the ``ccv-run-scan-sub`` subscription and calls
``execute_scan(scan_id)`` for each message received.
"""

from __future__ import annotations

import asyncio
import json
import os
import threading

from google.cloud import pubsub_v1

from shared.config import get_settings
from shared.gcp_auth import get_credentials
from shared.logging import get_logger, setup_logging

from scan_runner.runner import execute_scan

logger = get_logger(__name__)


def _callback(message: pubsub_v1.subscriber.message.Message) -> None:
    """Handle a Pub/Sub message by extracting scan_id and running the scan."""
    try:
        data = json.loads(message.data.decode("utf-8"))
        scan_id = data.get("scan_id")

        if not scan_id:
            logger.warning("pubsub_message_no_scan_id", data=data)
            message.ack()
            return

        logger.info("pubsub_message_received", scan_id=scan_id)

        # Run the async execute_scan in an event loop
        loop = asyncio.new_event_loop()
        try:
            loop.run_until_complete(execute_scan(scan_id))
        finally:
            loop.close()

        message.ack()
        logger.info("pubsub_message_acked", scan_id=scan_id)

    except Exception as exc:
        logger.error("pubsub_message_handler_error", error=str(exc))
        # Nack so the message gets redelivered
        message.nack()


def main() -> None:
    settings = get_settings()
    setup_logging(settings.api_log_level)

    project_id = settings.pubsub_project_id or settings.google_cloud_project
    topic_name = settings.pubsub_topic_run_scan  # "ccv-run-scan"
    subscription_name = os.getenv("PUBSUB_RUN_SCAN_SUBSCRIPTION", f"{topic_name}-sub")

    credentials = get_credentials()
    if credentials:
        subscriber = pubsub_v1.SubscriberClient(credentials=credentials)
    else:
        subscriber = pubsub_v1.SubscriberClient()
    subscription_path = subscriber.subscription_path(project_id, subscription_name)

    logger.info(
        "scan_subscriber_start",
        subscription=subscription_path,
        topic=topic_name,
    )

    # Start pulling messages
    streaming_pull = subscriber.subscribe(subscription_path, callback=_callback)
    print(f"Listening for messages on {subscription_path} ...")

    # Block the main thread
    try:
        streaming_pull.result()
    except KeyboardInterrupt:
        streaming_pull.cancel()
        streaming_pull.result()  # Wait for cleanup
        logger.info("scan_subscriber_stopped")


if __name__ == "__main__":
    main()
