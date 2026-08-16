"""Server-owned authorization and capture for grocery-provider tool calls."""

from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, Dict, Iterator, Set


class CommercePermission(StrEnum):
    READ = "read"
    CART_WRITE = "cart_write"
    CHECKOUT = "checkout"


@dataclass(frozen=True)
class CommerceAuthority:
    """Unforgeable-by-the-model authority attached by a backend entrypoint."""

    source: str
    permissions: frozenset[CommercePermission]
    operation_id: str


@dataclass
class CommerceRunCapture:
    """Request-local intent and exact MCP results captured outside model text."""

    native_items: list[Dict[str, Any]] = field(default_factory=list)
    selected_address_id: str = ""
    user_instruction: str = ""
    tool_results: Dict[str, list[Any]] = field(default_factory=dict)
    tool_arguments: Dict[str, list[Dict[str, Any]]] = field(default_factory=dict)
    structured_result: Dict[str, Any] | None = None

    def record_tool_result(self, tool_name: str, result: Any) -> None:
        self.tool_results.setdefault(tool_name, []).append(result)

    def record_tool_arguments(self, tool_name: str, arguments: Dict[str, Any]) -> None:
        self.tool_arguments.setdefault(tool_name, []).append(dict(arguments))

    def latest(self, tool_name: str) -> Any:
        values = self.tool_results.get(tool_name) or []
        return values[-1] if values else None


_AUTHORITY: ContextVar[CommerceAuthority | None] = ContextVar(
    "kitch_commerce_authority",
    default=None,
)
_CAPTURE: ContextVar[CommerceRunCapture | None] = ContextVar(
    "kitch_commerce_capture",
    default=None,
)


class CommercePolicyError(PermissionError):
    def __init__(self, tool_name: str, message: str) -> None:
        super().__init__(message)
        self.tool_name = tool_name
        self.code = "commerce_tool_denied"


class CommerceToolPolicy:
    """Fail-closed policy shared by agentic and direct MCP execution."""

    READ_TOOLS: Set[str] = {
        "get_addresses",
        "search_products",
        "your_go_to_items",
        "get_cart",
        "get_payment_options",
        "get_orders",
        "get_order_details",
        "track_order",
        "check_payment_status",
    }
    CART_WRITE_TOOLS: Set[str] = {"update_cart"}
    CHECKOUT_TOOLS: Set[str] = {"checkout", "confirm_order"}
    AGENT_LOCAL_TOOLS: Set[str] = {
        "read_scoped_native_cart_tool",
        "search_ordering_preferences_tool",
        "store_ordering_preference_tool",
        "record_instamart_cart_result_tool",
    }

    @classmethod
    def authorize(cls, tool_name: str) -> None:
        name = str(tool_name or "").strip()
        authority = _AUTHORITY.get()
        if name in cls.AGENT_LOCAL_TOOLS:
            if authority is None:
                raise CommercePolicyError(name, "Commerce request authority is missing.")
            return
        if name in cls.READ_TOOLS:
            # Provider reads are safe for readiness/address/status paths even
            # when they are not part of an agent operation.
            return
        if name in cls.CART_WRITE_TOOLS:
            if authority and CommercePermission.CART_WRITE in authority.permissions:
                return
            raise CommercePolicyError(name, "Provider cart mutation is not authorized for this request.")
        if name in cls.CHECKOUT_TOOLS:
            if (
                authority
                and authority.source == "ui_place_order"
                and CommercePermission.CHECKOUT in authority.permissions
            ):
                return
            raise CommercePolicyError(name, "Checkout is available only to the approved UI place-order endpoint.")
        # Unknown provider mutations and newly discovered tools are denied.
        raise CommercePolicyError(name, f"Provider tool '{name}' is not allowlisted by Kitch.")


@contextmanager
def commerce_request_context(
    *,
    source: str,
    permissions: Set[CommercePermission],
    operation_id: str,
    capture: CommerceRunCapture | None = None,
) -> Iterator[CommerceRunCapture | None]:
    authority_token = _AUTHORITY.set(
        CommerceAuthority(
            source=source,
            permissions=frozenset(permissions),
            operation_id=operation_id,
        )
    )
    capture_token = _CAPTURE.set(capture)
    try:
        yield capture
    finally:
        _CAPTURE.reset(capture_token)
        _AUTHORITY.reset(authority_token)


def current_commerce_capture() -> CommerceRunCapture:
    capture = _CAPTURE.get()
    if capture is None:
        raise CommercePolicyError("local_context", "Commerce request capture is missing.")
    return capture


def current_commerce_authority() -> CommerceAuthority | None:
    return _AUTHORITY.get()
