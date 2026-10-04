"""Household-scoped ADK memory configuration and agent tools.

Kitch keeps conversational sessions process-local, but can persist selected
household kitchen context in Vertex AI Memory Bank.  This module is the only
place that selects the memory backend and defines the scope used for reads and
writes.
"""

from __future__ import annotations

import asyncio
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
import logging
import os
import time
from typing import Any, Callable
from uuid import uuid4

from google.adk.events import Event
from google.adk.memory import InMemoryMemoryService
from google.adk.memory.base_memory_service import BaseMemoryService, SearchMemoryResponse
from google.adk.tools import ToolContext
from google.genai.types import Content, Part

from app.household_config import get_household_profile_id


MEMORY_APP_NAME = "kitch"
MEMORY_BACKENDS = frozenset({"in_memory", "vertex_express"})
MEMORY_READINESS_TIMEOUT_SECONDS = 8.0

logger = logging.getLogger(__name__)


class MemoryUnavailableError(RuntimeError):
    """Raised when the configured memory backend cannot accept an operation."""


class UnavailableMemoryService(BaseMemoryService):
    """Fail-explicit service used when persistent memory is misconfigured.

    Keeping this object on the Runner lets unrelated Kitch capabilities remain
    usable.  It is deliberately not an in-memory fallback.
    """

    def __init__(self, diagnostic: str) -> None:
        self.diagnostic = diagnostic

    async def add_session_to_memory(self, session: Any) -> None:
        del session
        raise MemoryUnavailableError(self.diagnostic)

    async def add_events_to_memory(
        self,
        *,
        app_name: str,
        user_id: str,
        events: Sequence[Event],
        session_id: str | None = None,
        custom_metadata: Mapping[str, object] | None = None,
    ) -> None:
        del app_name, user_id, events, session_id, custom_metadata
        raise MemoryUnavailableError(self.diagnostic)

    async def search_memory(
        self,
        *,
        app_name: str,
        user_id: str,
        query: str,
    ) -> SearchMemoryResponse:
        del app_name, user_id, query
        raise MemoryUnavailableError(self.diagnostic)


def _safe_diagnostic(error: BaseException) -> str:
    """Return a credential-safe operator diagnostic without raw payloads."""
    if isinstance(error, (asyncio.TimeoutError, TimeoutError)):
        return "Memory Bank timed out."
    name = type(error).__name__.lower()
    text = str(error).lower()
    if any(token in name or token in text for token in ("auth", "credential", "permission", "401", "403")):
        return "Memory Bank authentication failed."
    if isinstance(error, (ImportError, ModuleNotFoundError)):
        return "The Vertex AI Memory Bank dependency is not installed."
    return "Memory Bank is unavailable."


def _memory_bank_engine_id(resource_id: str) -> str:
    """Accept either a bare engine ID or a fully-qualified resource name."""
    return resource_id.rstrip("/").split("/")[-1]


def _build_vertex_express_service(
    *, agent_engine_id: str, express_mode_api_key: str
) -> BaseMemoryService:
    """Build ADK Memory Bank without coupling Gemini's auth mode to memory.

    ADK 2.1.0's public constructor accepts a dedicated Express key but drops it
    when GOOGLE_GENAI_USE_VERTEXAI is false. Kitch intentionally uses AI Studio
    for Gemini and Vertex Express for memory at the same time. Because the ADK
    version is pinned, keep the compatibility adjustment isolated here until
    ADK decouples those credentials.
    """
    from google.adk.memory import VertexAiMemoryBankService

    service = VertexAiMemoryBankService(
        agent_engine_id=agent_engine_id,
        express_mode_api_key=express_mode_api_key,
    )
    if getattr(service, "_express_mode_api_key", None) != express_mode_api_key:
        service._express_mode_api_key = express_mode_api_key
    return service


@dataclass(frozen=True)
class MemoryRuntime:
    backend: str
    service: BaseMemoryService
    durable: bool
    configured: bool
    diagnostic: str

    @classmethod
    def from_environment(
        cls,
        environ: Mapping[str, str] | None = None,
        *,
        vertex_factory: Callable[..., BaseMemoryService] | None = None,
    ) -> "MemoryRuntime":
        env = os.environ if environ is None else environ
        configured_backend = str(env.get("KITCH_MEMORY_SERVICE", "") or "").strip()
        is_vercel = str(env.get("VERCEL", "")).strip().lower() in {
            "1",
            "true",
            "yes",
        }
        default_backend = (
            "vertex_express" if is_vercel else "in_memory"
        )
        backend = (configured_backend or default_backend).lower()
        if backend not in MEMORY_BACKENDS:
            diagnostic = (
                "KITCH_MEMORY_SERVICE must be either in_memory or vertex_express."
            )
            return cls(
                backend=backend or "invalid",
                service=UnavailableMemoryService(diagnostic),
                durable=False,
                configured=False,
                diagnostic=diagnostic,
            )

        if backend == "in_memory":
            return cls(
                backend=backend,
                service=InMemoryMemoryService(),
                durable=False,
                configured=True,
                diagnostic="Process-local memory is configured for development or tests.",
            )

        memory_bank_id = str(env.get("KITCH_MEMORY_BANK_ID", "") or "").strip()
        api_key = str(env.get("KITCH_MEMORY_BANK_API_KEY", "") or "").strip()
        missing = [
            name
            for name, value in (
                ("KITCH_MEMORY_BANK_ID", memory_bank_id),
                ("KITCH_MEMORY_BANK_API_KEY", api_key),
            )
            if not value
        ]
        if missing:
            diagnostic = "Persistent memory is missing required configuration: " + ", ".join(missing) + "."
            return cls(
                backend=backend,
                service=UnavailableMemoryService(diagnostic),
                durable=True,
                configured=False,
                diagnostic=diagnostic,
            )

        try:
            if vertex_factory is None:
                vertex_factory = _build_vertex_express_service
            service = vertex_factory(
                agent_engine_id=_memory_bank_engine_id(memory_bank_id),
                express_mode_api_key=api_key,
            )
        except Exception as error:  # configuration/dependency errors degrade memory only
            diagnostic = _safe_diagnostic(error)
            return cls(
                backend=backend,
                service=UnavailableMemoryService(diagnostic),
                durable=True,
                configured=False,
                diagnostic=diagnostic,
            )

        return cls(
            backend=backend,
            service=service,
            durable=True,
            configured=True,
            diagnostic="Persistent household memory is configured.",
        )

    async def readiness(self) -> dict[str, Any]:
        if not self.configured:
            return {
                "backend": self.backend,
                "state": "degraded",
                "durable": self.durable,
                "diagnostic": self.diagnostic,
            }
        if self.backend == "in_memory":
            return {
                "backend": self.backend,
                "state": "ready",
                "durable": False,
                "diagnostic": self.diagnostic,
            }

        started = time.perf_counter()
        try:
            await asyncio.wait_for(
                self.service.search_memory(
                    app_name=MEMORY_APP_NAME,
                    user_id=get_household_profile_id(),
                    query="household kitchen context",
                ),
                timeout=MEMORY_READINESS_TIMEOUT_SECONDS,
            )
        except Exception as error:
            _log_operation("health", self.backend, "degraded", started)
            return {
                "backend": self.backend,
                "state": "degraded",
                "durable": True,
                "diagnostic": _safe_diagnostic(error),
            }
        _log_operation("health", self.backend, "success", started)
        return {
            "backend": self.backend,
            "state": "ready",
            "durable": True,
            "diagnostic": "Memory Bank is reachable.",
        }


memory_runtime = MemoryRuntime.from_environment()
memory_service = memory_runtime.service


def _log_operation(operation: str, backend: str, outcome: str, started: float) -> None:
    logger.info(
        "memory_operation operation=%s backend=%s outcome=%s latency_ms=%d",
        operation,
        backend,
        outcome,
        round((time.perf_counter() - started) * 1000),
    )


def _resolve_memory_service(tool_context: ToolContext | None) -> BaseMemoryService:
    if tool_context is not None:
        try:
            invocation_context = tool_context.get_invocation_context()
            service = getattr(invocation_context, "memory_service", None)
            if service is not None:
                return service
        except Exception:
            pass
        try:
            invocation_context = tool_context._invocation_context
            service = getattr(invocation_context, "memory_service", None)
            if service is not None:
                return service
        except Exception:
            pass
    return memory_service


def _memory_text(memory: Any) -> str:
    content = getattr(memory, "content", None)
    parts = getattr(content, "parts", None) or []
    return " ".join(
        str(getattr(part, "text", "") or "").strip()
        for part in parts
        if str(getattr(part, "text", "") or "").strip()
    ).strip()


async def update_household_memory_tool(
    statement: str,
    tool_context: ToolContext | None = None,
) -> dict[str, Any]:
    """Submit one durable natural-language household kitchen statement.

    The statement may express a preference, constraint, correction, or request
    to forget.  Memory Bank—not this tool—decides whether to create, revise,
    consolidate, or remove a memory.
    """
    normalized = str(statement or "").strip()
    if not normalized:
        return {
            "status": "error",
            "message": "No household memory statement was provided.",
        }

    service = _resolve_memory_service(tool_context)
    backend = memory_runtime.backend if service is memory_service else type(service).__name__
    started = time.perf_counter()
    event = Event(
        id=f"household_memory_{uuid4().hex}",
        content=Content(role="user", parts=[Part(text=normalized)]),
        author="user",
        timestamp=time.time(),
    )
    try:
        await service.add_events_to_memory(
            app_name=MEMORY_APP_NAME,
            user_id=get_household_profile_id(),
            events=[event],
            custom_metadata={"wait_for_completion": True},
        )
    except Exception as error:
        _log_operation("write", backend, "error", started)
        return {
            "status": "error",
            "message": _safe_diagnostic(error) + " The household context was not saved.",
        }

    _log_operation("write", backend, "success", started)
    return {
        "status": "success",
        "message": "Household memory was updated.",
    }


async def search_household_memory_tool(
    query: str,
    tool_context: ToolContext | None = None,
) -> dict[str, Any]:
    """Semantically search household kitchen memory for relevant facts."""
    normalized = str(query or "").strip()
    if not normalized:
        return {"status": "error", "message": "A memory search query is required.", "memories": []}

    service = _resolve_memory_service(tool_context)
    backend = memory_runtime.backend if service is memory_service else type(service).__name__
    started = time.perf_counter()
    try:
        result = await service.search_memory(
            app_name=MEMORY_APP_NAME,
            user_id=get_household_profile_id(),
            query=normalized,
        )
    except Exception as error:
        _log_operation("search", backend, "error", started)
        return {
            "status": "error",
            "message": _safe_diagnostic(error) + " Household context could not be recalled.",
            "memories": [],
        }

    memories = []
    for memory in result.memories or []:
        text = _memory_text(memory)
        if text:
            memories.append(
                {
                    "text": text,
                    "updated_at": getattr(memory, "timestamp", None),
                }
            )
    _log_operation("search", backend, "success", started)
    return {"status": "success", "memories": memories}


async def memory_readiness() -> dict[str, Any]:
    """Return the independent memory component used by readiness output."""
    return await memory_runtime.readiness()
