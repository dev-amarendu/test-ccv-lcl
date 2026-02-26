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
import concurrent.futures

from google.cloud import pubsub_v1

from shared.config import get_settings
from shared.gcp_auth import get_credentials
from shared.logging import get_logger, setup_logging

from scan_runner.runner import execute_scan

logger = get_logger(__name__)

# Single event loop running in a background thread — all async work goes here
_loop: asyncio.AbstractEventLoop | None = None
_executor: concurrent.futures.ThreadPoolExecutor | None = None


def _get_loop() -> asyncio.AbstractEventLoop:
    """Return a persistent event loop running in a background thread."""
    global _loop, _executor
    if _loop is None or _loop.is_closed():
        _loop = asyncio.new_event_loop()
        _executor = concurrent.futures.ThreadPoolExecutor(max_workers=1)
        _executor.submit(_run_loop, _loop)
    return _loop


def _run_loop(loop: asyncio.AbstractEventLoop) -> None:
    """Run the event loop forever in a background thread."""
    asyncio.set_event_loop(loop)
    loop.run_forever()


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

        # Submit the async work to the persistent event loop
        loop = _get_loop()
        future = asyncio.run_coroutine_threadsafe(execute_scan(scan_id), loop)
        # Wait for completion (blocking in the callback thread is fine —
        # Pub/Sub subscriber uses its own thread pool)
        future.result()

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
        # Stop the background event loop
        loop = _get_loop()
        loop.call_soon_threadsafe(loop.stop)
        logger.info("scan_subscriber_stopped")


if __name__ == "__main__":
    main()
