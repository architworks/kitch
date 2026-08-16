"""Shared streamable-HTTP MCP transport for grocery providers."""

from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import timedelta
from typing import Any, AsyncIterator, Dict

from app.telemetry import provider_operation_span
from app.commerce_policy import CommerceToolPolicy


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
            from mcp.client.streamable_http import streamablehttp_client
        except ImportError as exc:
            raise RuntimeError("Python MCP streamable HTTP support is not installed.") from exc

        headers = {"Authorization": f"Bearer {self.access_token}"}
        client_context = streamablehttp_client(
            self.url,
            headers=headers,
            timeout=timedelta(seconds=self.timeout_seconds),
            sse_read_timeout=timedelta(seconds=300),
        )
        async with client_context as (read, write, _):
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
