"""Request-scoped bridge from agent tools to frontend confirmation actions."""

from __future__ import annotations

from contextvars import ContextVar, Token
from typing import Any


_requested_action: ContextVar[dict[str, Any] | None] = ContextVar(
    "requested_agent_confirmation", default=None
)


def begin_confirmation_scope() -> Token:
    return _requested_action.set(None)


def record_confirmation(action: dict[str, Any]) -> None:
    _requested_action.set(action)


def requested_confirmation() -> dict[str, Any] | None:
    return _requested_action.get()


def end_confirmation_scope(token: Token) -> None:
    _requested_action.reset(token)
