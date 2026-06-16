"""Optional OpenTelemetry setup for ADK traces."""

from __future__ import annotations

import os


_OTEL_ENDPOINT_ENV_KEYS = (
    "OTEL_EXPORTER_OTLP_ENDPOINT",
    "OTEL_EXPORTER_OTLP_TRACES_ENDPOINT",
    "OTEL_EXPORTER_OTLP_METRICS_ENDPOINT",
    "OTEL_EXPORTER_OTLP_LOGS_ENDPOINT",
)


def _env_flag_enabled(name: str) -> bool:
    return os.environ.get(name, "").strip().lower() in {"1", "true", "yes", "on"}


def _env_flag_disabled(name: str) -> bool:
    return os.environ.get(name, "").strip().lower() in {"0", "false", "no", "off"}


def configure_adk_tracing() -> bool:
    """Configure ADK OpenTelemetry exporters when tracing is requested.

    ADK emits traces through OpenTelemetry. The exporter is enabled by setting
    standard OTEL endpoint variables, or by setting KITCH_ADK_TRACING_ENABLED.
    """
    if _env_flag_disabled("KITCH_ADK_TRACING_ENABLED"):
        return False

    has_otel_endpoint = any(os.environ.get(key) for key in _OTEL_ENDPOINT_ENV_KEYS)
    if not has_otel_endpoint and not _env_flag_enabled("KITCH_ADK_TRACING_ENABLED"):
        return False

    os.environ.setdefault("OTEL_SERVICE_NAME", "kitch-backend")
    os.environ.setdefault(
        "OTEL_RESOURCE_ATTRIBUTES",
        "service.namespace=kitch,deployment.environment=local",
    )

    try:
        from google.adk.telemetry.setup import maybe_set_otel_providers

        maybe_set_otel_providers()
        print("[Kitch tracing] ADK OpenTelemetry tracing configured.")
        return True
    except Exception as exc:
        message = f"[Kitch tracing] Failed to configure ADK OpenTelemetry tracing: {exc}"
        if _env_flag_enabled("KITCH_ADK_TRACING_REQUIRED"):
            raise RuntimeError(message) from exc
        print(message)
        return False
