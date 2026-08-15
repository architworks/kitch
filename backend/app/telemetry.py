"""Optional OpenTelemetry setup for ADK traces."""

from __future__ import annotations

import os
from contextlib import contextmanager
from typing import Iterator


_OTEL_ENDPOINT_ENV_KEYS = (
    "OTEL_EXPORTER_OTLP_ENDPOINT",
    "OTEL_EXPORTER_OTLP_TRACES_ENDPOINT",
    "OTEL_EXPORTER_OTLP_METRICS_ENDPOINT",
    "OTEL_EXPORTER_OTLP_LOGS_ENDPOINT",
)

_LANGSMITH_OTEL_ENDPOINT = "https://api.smith.langchain.com/otel/v1/traces"


def _env_flag_enabled(name: str) -> bool:
    return os.environ.get(name, "").strip().lower() in {"1", "true", "yes", "on"}


def _env_flag_disabled(name: str) -> bool:
    return os.environ.get(name, "").strip().lower() in {"0", "false", "no", "off"}


def _langsmith_api_key() -> str:
    return (
        os.environ.get("LANGSMITH_API_KEY")
        or os.environ.get("LANGCHAIN_API_KEY")
        or ""
    ).strip()


def _langsmith_enabled() -> bool:
    if _env_flag_disabled("KITCH_LANGSMITH_TRACING_ENABLED"):
        return False
    return bool(_langsmith_api_key()) or _env_flag_enabled("KITCH_LANGSMITH_TRACING_ENABLED")


def _langsmith_otel_hooks():
    api_key = _langsmith_api_key()
    if not api_key:
        if _env_flag_enabled("KITCH_LANGSMITH_TRACING_ENABLED"):
            raise RuntimeError("KITCH_LANGSMITH_TRACING_ENABLED is true, but LANGSMITH_API_KEY is not set.")
        return None

    from google.adk.telemetry.setup import OTelHooks
    from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
    from opentelemetry.sdk.trace.export import BatchSpanProcessor

    headers = {"x-api-key": api_key}
    project = (
        os.environ.get("LANGSMITH_PROJECT")
        or os.environ.get("LANGCHAIN_PROJECT")
        or ""
    ).strip()
    if project:
        headers["Langsmith-Project"] = project

    endpoint = (
        os.environ.get("LANGSMITH_OTEL_TRACES_ENDPOINT")
        or os.environ.get("LANGSMITH_OTEL_ENDPOINT")
        or _LANGSMITH_OTEL_ENDPOINT
    ).strip()

    exporter = OTLPSpanExporter(endpoint=endpoint, headers=headers)
    return OTelHooks(span_processors=[BatchSpanProcessor(exporter)])


def configure_adk_tracing() -> bool:
    """Configure ADK OpenTelemetry exporters when tracing is requested.

    ADK emits traces through OpenTelemetry. The exporter is enabled by setting
    standard OTEL endpoint variables, or by setting KITCH_ADK_TRACING_ENABLED.
    """
    if _env_flag_disabled("KITCH_ADK_TRACING_ENABLED"):
        return False

    has_otel_endpoint = any(os.environ.get(key) for key in _OTEL_ENDPOINT_ENV_KEYS)
    has_langsmith = _langsmith_enabled()
    if not has_otel_endpoint and not has_langsmith and not _env_flag_enabled("KITCH_ADK_TRACING_ENABLED"):
        return False

    os.environ.setdefault("OTEL_SERVICE_NAME", "kitch-backend")
    os.environ.setdefault(
        "OTEL_RESOURCE_ATTRIBUTES",
        "service.namespace=kitch,deployment.environment=local",
    )

    try:
        from google.adk.telemetry.setup import maybe_set_otel_providers

        hooks = []
        langsmith_hooks = _langsmith_otel_hooks() if has_langsmith else None
        if langsmith_hooks:
            hooks.append(langsmith_hooks)

        maybe_set_otel_providers(hooks)
        print("[Kitch tracing] ADK OpenTelemetry tracing configured.")
        return True
    except Exception as exc:
        message = f"[Kitch tracing] Failed to configure ADK OpenTelemetry tracing: {exc}"
        if _env_flag_enabled("KITCH_ADK_TRACING_REQUIRED"):
            raise RuntimeError(message) from exc
        print(message)
        return False


@contextmanager
def provider_operation_span(
    provider: str,
    environment: str,
    operation: str,
) -> Iterator[object]:
    """Trace safe provider metadata without tokens, addresses, or payloads."""
    try:
        from opentelemetry import trace

        with trace.get_tracer("kitch.providers").start_as_current_span(
            "grocery_provider.operation",
            attributes={
                "grocery.provider": provider,
                "deployment.environment": environment,
                "grocery.operation": operation,
            },
        ) as span:
            yield span
    except ImportError:
        yield object()
