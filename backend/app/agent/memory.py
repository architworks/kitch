"""Household-scoped ADK memory configuration and agent tools.

Kitch keeps conversational sessions process-local, but can persist selected
household kitchen context in Vertex AI Memory Bank.  This module is the only
place that selects the memory backend and defines the scope used for reads and
writes.
"""

from __future__ import annotations

import asyncio
from collections.abc import Mapping, Sequence
from contextvars import ContextVar, Token
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
MEMORY_BACKENDS = frozenset({"in_memory", "vertex"})
# The first ADC/WIF token exchange after a cold start can take several seconds.
# Keep the probe bounded without reporting a healthy Memory Bank as degraded.
MEMORY_READINESS_TIMEOUT_SECONDS = 20.0

_vercel_oidc_token: ContextVar[str | None] = ContextVar(
    "kitch_vercel_oidc_token", default=None
)

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


class _VercelOidcTokenSupplier:
    """Supply the signed Vercel token associated with the current request."""

    def get_subject_token(self, context: Any, request: Any) -> str:
        del context, request
        token = _vercel_oidc_token.get() or os.environ.get("VERCEL_OIDC_TOKEN", "")
        if not token:
            from google.auth.exceptions import RefreshError

            raise RefreshError("The Vercel OIDC token is unavailable for this request.")
        return token


def begin_memory_auth_scope(vercel_oidc_token: str | None) -> Token:
    """Bind an optional Vercel identity token to the current HTTP request."""
    return _vercel_oidc_token.set(vercel_oidc_token or None)


def end_memory_auth_scope(token: Token) -> None:
    _vercel_oidc_token.reset(token)


def _build_vercel_credentials(
    *,
    project_number: str,
    pool_id: str,
    provider_id: str,
    service_account_email: str,
) -> Any:
    """Exchange Vercel OIDC for short-lived Google service-account access."""
    from google.auth import identity_pool

    audience = (
        "//iam.googleapis.com/projects/"
        f"{project_number}/locations/global/workloadIdentityPools/"
        f"{pool_id}/providers/{provider_id}"
    )
    return identity_pool.Credentials(
        audience=audience,
        subject_token_type="urn:ietf:params:oauth:token-type:jwt",
        subject_token_supplier=_VercelOidcTokenSupplier(),
        service_account_impersonation_url=(
            "https://iamcredentials.googleapis.com/v1/projects/-/serviceAccounts/"
            f"{service_account_email}:generateAccessToken"
        ),
        scopes=["https://www.googleapis.com/auth/cloud-platform"],
    )


def _build_vertex_service(
    *,
    project: str,
    location: str,
    agent_engine_id: str,
    credentials_factory: Callable[[], Any] | None = None,
) -> BaseMemoryService:
    """Build standard Vertex Memory Bank with ADC or request-scoped WIF."""
    from google.adk.memory import VertexAiMemoryBankService

    if credentials_factory is None:
        return VertexAiMemoryBankService(
            project=project,
            location=location,
            agent_engine_id=agent_engine_id,
        )

    class RequestScopedVertexMemoryBankService(VertexAiMemoryBankService):
        def _get_api_client(self):
            import vertexai

            return vertexai.Client(
                project=self._project,
                location=self._location,
                credentials=credentials_factory(),
            ).aio

    return RequestScopedVertexMemoryBankService(
        project=project,
        location=location,
        agent_engine_id=agent_engine_id,
    )


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
        default_backend = "vertex" if is_vercel else "in_memory"
        backend = (configured_backend or default_backend).lower()
        if backend not in MEMORY_BACKENDS:
            diagnostic = (
                "KITCH_MEMORY_SERVICE must be either in_memory or vertex."
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
        project = str(
            env.get("GOOGLE_CLOUD_PROJECT", "")
            or env.get("GCP_PROJECT_ID", "")
            or ""
        ).strip()
        location = str(env.get("GOOGLE_CLOUD_LOCATION", "") or "").strip()
        missing = [
            name
            for name, value in (
                ("KITCH_MEMORY_BANK_ID", memory_bank_id),
                ("GOOGLE_CLOUD_PROJECT", project),
                ("GOOGLE_CLOUD_LOCATION", location),
            )
            if not value
        ]
        credentials_factory: Callable[[], Any] | None = None
        if is_vercel:
            wif_values = {
                "GCP_PROJECT_NUMBER": str(env.get("GCP_PROJECT_NUMBER", "") or "").strip(),
                "GCP_WORKLOAD_IDENTITY_POOL_ID": str(
                    env.get("GCP_WORKLOAD_IDENTITY_POOL_ID", "") or ""
                ).strip(),
                "GCP_WORKLOAD_IDENTITY_POOL_PROVIDER_ID": str(
                    env.get("GCP_WORKLOAD_IDENTITY_POOL_PROVIDER_ID", "") or ""
                ).strip(),
                "GCP_SERVICE_ACCOUNT_EMAIL": str(
                    env.get("GCP_SERVICE_ACCOUNT_EMAIL", "") or ""
                ).strip(),
            }
            missing.extend(name for name, value in wif_values.items() if not value)
            if not missing:
                credentials_factory = lambda: _build_vercel_credentials(
                    project_number=wif_values["GCP_PROJECT_NUMBER"],
                    pool_id=wif_values["GCP_WORKLOAD_IDENTITY_POOL_ID"],
                    provider_id=wif_values["GCP_WORKLOAD_IDENTITY_POOL_PROVIDER_ID"],
                    service_account_email=wif_values["GCP_SERVICE_ACCOUNT_EMAIL"],
                )
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
                vertex_factory = _build_vertex_service
            service = vertex_factory(
                project=project,
                location=location,
                agent_engine_id=_memory_bank_engine_id(memory_bank_id),
                credentials_factory=credentials_factory,
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
