"""Structured logging with request_id propagation."""

from __future__ import annotations

import contextvars
import logging
import uuid

import structlog

request_id_ctx: contextvars.ContextVar[str] = contextvars.ContextVar(
    "request_id", default=""
)


def get_request_id() -> str:
    """Return current request id, generating one if absent."""
    rid = request_id_ctx.get()
    if not rid:
        rid = uuid.uuid4().hex[:16]
        request_id_ctx.set(rid)
    return rid


def set_request_id(rid: str) -> None:
    request_id_ctx.set(rid)


def _add_request_id(
    logger: logging.Logger,  # noqa: ARG001
    method_name: str,  # noqa: ARG001
    event_dict: dict,
) -> dict:
    rid = request_id_ctx.get()
    if rid:
        event_dict["request_id"] = rid
    return event_dict


def setup_logging(log_level: str = "info") -> None:
    """Configure structlog + stdlib root logger."""
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            _add_request_id,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.dev.ConsoleRenderer()
            if log_level == "debug"
            else structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(
            getattr(logging, log_level.upper(), logging.INFO)
        ),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )
    logging.basicConfig(level=getattr(logging, log_level.upper(), logging.INFO))


def get_logger(name: str | None = None) -> structlog.stdlib.BoundLogger:
    return structlog.get_logger(name)
