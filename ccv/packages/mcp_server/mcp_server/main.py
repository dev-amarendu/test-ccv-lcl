"""MCP Server FastAPI application."""

from __future__ import annotations

import time
import uuid

import httpx
from fastapi import FastAPI, Request, Response

from shared.config import get_settings
from shared.logging import get_logger, set_request_id, setup_logging
from shared.schemas import MCPCallRequest, MCPCallResponse

from mcp_server.auth import verify_mcp_token
from mcp_server.audit import log_mcp_call
from mcp_server.rate_limit import check_rate_limit
from mcp_server.registry import get_tool_registry

settings = get_settings()
setup_logging(settings.api_log_level)
logger = get_logger(__name__)

app = FastAPI(title="CCV MCP Server", version="0.1.0")


@app.middleware("http")
async def request_id_middleware(request: Request, call_next) -> Response:
    rid = request.headers.get("x-request-id") or uuid.uuid4().hex[:16]
    set_request_id(rid)
    response: Response = await call_next(request)
    response.headers["X-Request-Id"] = rid
    return response


@app.get("/health")
async def health() -> dict:
    return {"status": "ok", "service": "ccv-mcp"}


@app.post("/mcp/v1/call", response_model=MCPCallResponse)
async def mcp_call(body: MCPCallRequest, request: Request) -> MCPCallResponse:
    """Execute an MCP tool call."""
    request_id = body.request_id or uuid.uuid4().hex[:16]
    set_request_id(request_id)

    # Auth
    auth_header = request.headers.get("authorization", "")
    verify_mcp_token(auth_header)

    # Rate limiting
    check_rate_limit(body.caller or "anonymous", body.tool_name)

    registry = get_tool_registry()
    start = time.monotonic()

    if body.tool_name not in registry:
        elapsed = (time.monotonic() - start) * 1000
        resp = MCPCallResponse(
            request_id=request_id,
            tool_name=body.tool_name,
            ok=False,
            error=f"Unknown tool: {body.tool_name}",
            latency_ms=round(elapsed, 2),
            retriable=False,
        )
        await log_mcp_call(request_id, body, resp)
        return resp

    tool_fn = registry[body.tool_name]
    try:
        result = await tool_fn(body.params)
        elapsed = (time.monotonic() - start) * 1000
        resp = MCPCallResponse(
            request_id=request_id,
            tool_name=body.tool_name,
            ok=True,
            result=result,
            latency_ms=round(elapsed, 2),
            retriable=False,
        )
    except (httpx.TimeoutException, httpx.ConnectError, httpx.NetworkError, OSError) as exc:
        elapsed = (time.monotonic() - start) * 1000
        logger.error(
            "mcp_tool_transient_error",
            tool=body.tool_name,
            error=str(exc),
            retriable=True,
        )
        resp = MCPCallResponse(
            request_id=request_id,
            tool_name=body.tool_name,
            ok=False,
            error=str(exc),
            latency_ms=round(elapsed, 2),
            retriable=True,
        )
    except Exception as exc:
        elapsed = (time.monotonic() - start) * 1000
        logger.error("mcp_tool_error", tool=body.tool_name, error=str(exc))
        resp = MCPCallResponse(
            request_id=request_id,
            tool_name=body.tool_name,
            ok=False,
            error=str(exc),
            latency_ms=round(elapsed, 2),
            retriable=False,
        )

    await log_mcp_call(request_id, body, resp)
    return resp


def main() -> None:
    import uvicorn

    uvicorn.run(
        "mcp_server.main:app",
        host=settings.mcp_host,
        port=settings.mcp_port,
        log_level=settings.api_log_level,
        reload=True,
    )


if __name__ == "__main__":
    main()
