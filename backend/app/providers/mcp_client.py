"""Shared streamable-HTTP MCP transport for grocery providers."""

from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import timedelta
from typing import Any, AsyncIterator, Dict

from app.telemetry import provider_operation_span
from app.commerce_policy import CommerceToolPolicy


@asynccontextmanager
async def streamable_http_transport(
    url: str,
    *,
    headers: Dict[str, str] | None = None,
    timeout_seconds: int = 30,
    sse_read_timeout_seconds: int = 300,
) -> AsyncIterator[tuple[Any, Any]]:
    """Open streamable HTTP across the MCP 1.x and 2.x client APIs."""
    try:
        from mcp.client.streamable_http import streamable_http_client
        from mcp.shared._httpx_utils import create_mcp_http_client
        import httpx2
    except ImportError:
        try:
            from mcp.client.streamable_http import streamablehttp_client
        except ImportError as exc:
            raise RuntimeError(
                "Python MCP streamable HTTP support is not installed."
            ) from exc

        async with streamablehttp_client(
            url,
            headers=headers,
            timeout=timedelta(seconds=timeout_seconds),
            sse_read_timeout=timedelta(seconds=sse_read_timeout_seconds),
        ) as streams:
            yield streams[0], streams[1]
        return

    http_client = create_mcp_http_client(
        headers=headers,
        timeout=httpx2.Timeout(
            timeout_seconds,
            read=sse_read_timeout_seconds,
        ),
    )
    async with http_client:
        async with streamable_http_client(
            url,
            http_client=http_client,
        ) as streams:
            yield streams[0], streams[1]


def to_plain(value: Any) -> Any:
    if hasattr(value, "model_dump"):
        return value.model_dump(mode="json")
    if isinstance(value, list):
        return [to_plain(item) for item in value]
    if isinstance(value, dict):
        return {str(key): to_plain(child) for key, child in value.items()}
    return value


class McpProviderClient:
    def __init__(
        self,
        *,
        url: str,
        access_token: str,
        provider_id: str = "unknown",
        environment: str = "unknown",
        timeout_seconds: int = 30,
    ) -> None:
        self.url = url
        self.access_token = access_token
        self.timeout_seconds = timeout_seconds
        self.provider_id = provider_id
        self.environment = environment

    @asynccontextmanager
    async def session(self) -> AsyncIterator[Any]:
        try:
            from mcp import ClientSession
        except ImportError as exc:
            raise RuntimeError("Python MCP streamable HTTP support is not installed.") from exc

        headers = {"Authorization": f"Bearer {self.access_token}"}
        async with streamable_http_transport(
            self.url,
            headers=headers,
            timeout_seconds=self.timeout_seconds,
            sse_read_timeout_seconds=300,
        ) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                yield session

    async def list_tools(self, session: Any) -> Dict[str, Any]:
        result = await session.list_tools()
        return {tool.name: tool for tool in result.tools}

    async def call_tool(
        self,
        session: Any,
        name: str,
        arguments: Dict[str, Any] | None = None,
    ) -> Dict[str, Any]:
        CommerceToolPolicy.authorize(name)
        with provider_operation_span(self.provider_id, self.environment, name):
            return to_plain(await session.call_tool(name, arguments or {}))

    @staticmethod
    def input_schema(tool: Any) -> Dict[str, Any]:
        schema = getattr(tool, "inputSchema", None) or getattr(tool, "input_schema", None) or {}
        return to_plain(schema) if schema else {}
