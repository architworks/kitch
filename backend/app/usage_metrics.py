"""App-level usage metrics for AI requests.

One row per AI request: which feature names were used, how it ended, how long
it took, and how many model calls and tokens it used. Never message text,
photos, food, or anything from a grocery app: grocery-app activity is recorded
only as the generic feature "grocery_app". People and households are keyed by
a keyed hash, so the metrics count unique and returning users without naming
anyone. The dashboard reports aggregates only.
"""

from __future__ import annotations

import hashlib
import hmac
import os
import time
from contextvars import ContextVar, Token
from dataclasses import dataclass, field
from typing import Any, Dict

# Agent names mapped to the feature they serve.
AGENT_FEATURES = {
    "kitch_coordinator": "chat",
    "chef_planner": "meal_planning",
    "nutrition_tracker": "nutrition",
    "recipe_grocery_planner": "recipes_and_groceries",
    "recipe_detail_planner": "recipes_and_groceries",
    "vision_scanner": "photo",
    "pantry_reconciliation_mode": "pantry",
}
# Anything that touches a grocery app collapses to one generic feature, so no
# provider, product, cart or order detail is ever recorded.
GROCERY_APP_MARKERS = ("instamart", "provider", "swiggy")
GROCERY_APP_FEATURE = "grocery_app"


@dataclass
class UsageCollector:
    kind: str
    started: float = field(default_factory=time.monotonic)
    first_response_ms: int | None = None
    model_calls: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    outcome: str | None = None
    features: set[str] = field(default_factory=set)


_current: ContextVar[UsageCollector | None] = ContextVar("kitch_usage_collector", default=None)


def start_usage(kind: str) -> Token:
    return _current.set(UsageCollector(kind=kind))


def end_usage(token: Token) -> UsageCollector | None:
    collector = _current.get()
    _current.reset(token)
    return collector


def mark_outcome(outcome: str) -> None:
    """Let a handler say how a 200 response really ended (e.g. hit a limit)."""
    collector = _current.get()
    if collector is not None:
        collector.outcome = outcome


def _feature_for(name: str) -> str | None:
    lowered = name.lower()
    if any(marker in lowered for marker in GROCERY_APP_MARKERS):
        return GROCERY_APP_FEATURE
    return AGENT_FEATURES.get(name) or (name if name.endswith("_tool") else None)


def note_agent_event(event: Any) -> None:
    """Record names, timing and token counts from one agent event; never content."""
    collector = _current.get()
    if collector is None:
        return
    author = str(getattr(event, "author", "") or "")
    if author and author != "user":
        if collector.first_response_ms is None:
            collector.first_response_ms = int((time.monotonic() - collector.started) * 1000)
        feature = _feature_for(author)
        if feature:
            collector.features.add(feature)
    usage = getattr(event, "usage_metadata", None)
    if usage is not None:
        collector.model_calls += 1
        collector.input_tokens += int(getattr(usage, "prompt_token_count", 0) or 0)
        collector.output_tokens += int(getattr(usage, "candidates_token_count", 0) or 0)
        collector.output_tokens += int(getattr(usage, "thoughts_token_count", 0) or 0)
    if author.lower().startswith("instamart"):
        return  # grocery-app agents: no tool names, only the generic feature
    get_calls = getattr(event, "get_function_calls", None)
    for call in (get_calls() if callable(get_calls) else []) or []:
        feature = _feature_for(str(getattr(call, "name", "") or ""))
        if feature:
            collector.features.add(feature)


def pseudonym(kind: str, value: str) -> str | None:
    """Keyed hash of an account or household id; None when no key is configured."""
    secret = os.environ.get("KITCH_AUTH_SESSION_SECRET", "")
    if not secret or not value:
        return None
    return hmac.new(secret.encode(), f"usage:{kind}:{value}".encode(), hashlib.sha256).hexdigest()[:24]


def usage_row(collector: UsageCollector, status_code: int, user_key: str, household_key: str) -> Dict[str, Any]:
    if collector.outcome:
        outcome = collector.outcome
    elif status_code < 400:
        outcome = "ok"
    elif status_code == 429:
        outcome = "quota"
    elif status_code == 504:
        outcome = "limit"
    elif status_code < 500:
        outcome = "rejected"
    else:
        outcome = "error"
    return {
        "user_key": user_key,
        "household_key": household_key,
        "kind": collector.kind,
        "features": sorted(collector.features),
        "outcome": outcome,
        "duration_ms": int((time.monotonic() - collector.started) * 1000),
        "first_response_ms": collector.first_response_ms,
        "model_calls": collector.model_calls,
        "input_tokens": collector.input_tokens,
        "output_tokens": collector.output_tokens,
    }
