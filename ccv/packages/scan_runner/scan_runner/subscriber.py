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
import signal
import sys

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

        # Run async scan in an isolated event loop for this thread.
        # This prevents "loop already running" errors when concurrent messages arrive.
        asyncio.run(execute_scan(scan_id))

        message.ack()
        logger.info("pubsub_message_acked", scan_id=scan_id)

    except Exception as exc:
        # We catch all exceptions here. If execute_scan failed, it already updated 
        # Firestore. We ACK the message to prevent infinite Pub/Sub retries for
        # terminal failures (like coding errors or misconfigurations).
        logger.error("pubsub_message_handler_terminal_failure", error=str(exc))
        message.ack()


def main() -> None:
    settings = get_settings()
    setup_logging(settings.api_log_level)

    project_id = settings.pubsub_project_id or settings.google_cloud_project
    topic_name = settings.pubsub_topic_run_scan
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

    streaming_pull = subscriber.subscribe(subscription_path, callback=_callback)
    print(f"Listening for messages on {subscription_path} ...")
    print("Press Ctrl+C to stop.")

    # Handle Ctrl+C gracefully
    try:
        # Block in Python (time.sleep) rather than gRPC (streaming_pull.result)
        # to ensure KeyboardInterrupt can be raised cleanly on Ctrl+C.
        import time
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nShutting down gracefully...")
        streaming_pull.cancel()
        streaming_pull.result()  # Block until shutdown is complete
    except Exception as exc:
        logger.error("subscriber_error", error=str(exc))
        streaming_pull.cancel()
        streaming_pull.result()
    finally:
        sys.exit(0)


if __name__ == "__main__":
    main()
