"""MCP client helper — calls the MCP server's /mcp/v1/call endpoint."""

from __future__ import annotations

from typing import Any

import httpx

from shared.config import get_settings
from shared.logging import get_logger, get_request_id

logger = get_logger(__name__)


class MCPClient:
    """HTTP client for calling MCP tools via the MCP server."""

    def __init__(self) -> None:
        settings = get_settings()
        self.base_url = settings.mcp_base_url.rstrip("/")
        self.token = settings.mcp_internal_token

    async def call_tool(
        self,
        tool_name: str,
        params: dict[str, Any],
        timeout_ms: int = 60000,
        caller: str = "scan_runner",
    ) -> dict[str, Any]:
        """Call an MCP tool and return the result dict.

        Raises RuntimeError if the tool call fails.
        """
        request_id = get_request_id()

        payload = {
            "tool_name": tool_name,
            "params": params,
            "request_id": request_id,
            "caller": caller,
            "timeout_ms": timeout_ms,
        }

        headers = {
            "Content-Type": "application/json",
            "X-Request-Id": request_id,
        }
        if self.token and self.token != "changeme":
            headers["Authorization"] = f"Bearer {self.token}"

        async with httpx.AsyncClient(timeout=timeout_ms / 1000 + 10) as client:
            resp = await client.post(
                f"{self.base_url}/mcp/v1/call",
                json=payload,
                headers=headers,
            )

        resp.raise_for_status()
        data = resp.json()

        if not data.get("ok"):
            error_msg = data.get("error", "Unknown MCP error")
            logger.error("mcp_tool_call_failed", tool=tool_name, error=error_msg)
            raise RuntimeError(f"MCP tool {tool_name} failed: {error_msg}")

        logger.info("mcp_tool_call_ok", tool=tool_name, latency_ms=data.get("latency_ms"))
        return data.get("result", {})
