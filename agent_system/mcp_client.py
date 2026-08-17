"""Minimal MCP (Model Context Protocol) client used by Agent 3 to publish the
hourly run summary to an external MCP server (e.g. a dashboard or another
agent fleet listening for `tools/call` notifications).

This deliberately does not depend on a specific MCP SDK: it speaks the
protocol's JSON-RPC 2.0 shape directly over HTTP, which is enough for a
"publish this report" one-way call and keeps the dependency footprint small.
If `MCP_SERVER_URL` is not configured, `NoOpMCPClient` is used and the field
`mcp_published=False` in the output makes the skip visible rather than silent.
"""
from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from typing import Any

import httpx

from .config import settings

logger = logging.getLogger("agent_system.mcp")


class MCPClient(ABC):
    @abstractmethod
    def call_tool(self, tool_name: str, arguments: dict[str, Any]) -> tuple[bool, str | None]:
        """Returns (ok, error)."""


class NoOpMCPClient(MCPClient):
    def call_tool(self, tool_name: str, arguments: dict[str, Any]) -> tuple[bool, str | None]:
        logger.info("[MCP no-op] would call '%s' with %d keys", tool_name, len(arguments))
        return False, "MCP_SERVER_URL sozlanmagan — chaqiruv o'tkazib yuborildi"


class HttpMCPClient(MCPClient):
    def __init__(self, server_url: str):
        self._url = server_url.rstrip("/")

    def call_tool(self, tool_name: str, arguments: dict[str, Any]) -> tuple[bool, str | None]:
        payload = {
            "jsonrpc": "2.0",
            "id": f"lms-sync-{tool_name}",
            "method": "tools/call",
            "params": {"name": tool_name, "arguments": arguments},
        }
        try:
            with httpx.Client(timeout=15.0) as client:
                resp = client.post(self._url, json=payload)
            if resp.status_code == 200 and "error" not in resp.json():
                return True, None
            return False, f"MCP xatosi: HTTP {resp.status_code} {resp.text[:200]}"
        except (httpx.HTTPError, ValueError) as exc:
            return False, f"MCP ulanish xatosi: {exc}"


def get_mcp_client() -> MCPClient:
    if settings.mcp_server_url:
        return HttpMCPClient(settings.mcp_server_url)
    return NoOpMCPClient()
