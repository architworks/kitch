"""Provider-neutral grocery commerce contracts."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, List


@dataclass(frozen=True)
class ProviderCapabilities:
    saved_addresses: bool = False
    cart_sync: bool = False
    cart_revalidation: bool = False
    checkout: bool = False
    payment_status: bool = False
    order_history: bool = False
    order_tracking: bool = False

    def as_dict(self) -> Dict[str, bool]:
        return {
            "saved_addresses": self.saved_addresses,
            "cart_sync": self.cart_sync,
            "cart_revalidation": self.cart_revalidation,
            "checkout": self.checkout,
            "payment_status": self.payment_status,
            "order_history": self.order_history,
            "order_tracking": self.order_tracking,
        }


@dataclass(frozen=True)
class ProviderDescriptor:
    id: str
    label: str
    brand_label: str
    description: str
    enabled: bool
    state: str
    message: str
    environment: str = "production"
    badge: str | None = None
    requires_connection: bool = False
    production_gated: bool = False
    capabilities: ProviderCapabilities = field(default_factory=ProviderCapabilities)
    theme: Dict[str, str] = field(default_factory=dict)

    def as_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "label": self.label,
            "brand_label": self.brand_label,
            "description": self.description,
            "enabled": self.enabled,
            "state": self.state,
            "message": self.message,
            "environment": self.environment,
            "badge": self.badge,
            "requires_connection": self.requires_connection,
            "production_gated": self.production_gated,
            "capabilities": self.capabilities.as_dict(),
            "theme": dict(self.theme),
            "api_base": f"/api/grocery/providers/{self.id}",
        }


class ProviderOperationError(RuntimeError):
    """Safe, normalized provider failure that may cross the HTTP boundary."""

    def __init__(
        self,
        *,
        provider: str,
        operation: str,
        code: str,
        message: str,
        retryable: bool = False,
        status_code: int = 502,
        draft: Dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.provider = provider
        self.operation = operation
        self.code = code
        self.message = message
        self.retryable = retryable
        self.status_code = status_code
        self.draft = draft

    def public_detail(self) -> Dict[str, Any]:
        detail: Dict[str, Any] = {
            "code": self.code,
            "message": self.message,
            "provider": self.provider,
            "operation": self.operation,
            "retryable": self.retryable,
        }
        if self.draft is not None:
            detail["draft"] = self.draft
        return detail


class GroceryProviderAdapter(ABC):
    provider_id: str

    @abstractmethod
    def descriptor(self) -> ProviderDescriptor:
        raise NotImplementedError

    @abstractmethod
    async def list_addresses(self) -> Dict[str, Any]:
        raise NotImplementedError

    @abstractmethod
    async def sync_cart(
        self,
        items: List[Dict[str, Any]],
        selected_address_id: str = "",
    ) -> Dict[str, Any]:
        raise NotImplementedError

    @abstractmethod
    async def revalidate_cart(self, draft: Dict[str, Any]) -> Dict[str, Any]:
        raise NotImplementedError

    @abstractmethod
    async def get_cart(self) -> Dict[str, Any]:
        raise NotImplementedError

    @abstractmethod
    async def place_order(self, review: Dict[str, Any] | None = None) -> Dict[str, Any]:
        raise NotImplementedError

    async def payment_status(self, review: Dict[str, Any]) -> Dict[str, Any]:
        raise ProviderOperationError(
            provider=self.provider_id,
            operation="payment_status",
            code="payment_status_unsupported",
            message="This ordering provider does not expose a payment-status operation.",
            retryable=False,
            status_code=422,
        )

    async def readiness(self) -> Dict[str, Any]:
        descriptor = self.descriptor()
        if descriptor.production_gated or descriptor.state == "gated":
            state = "gated"
        elif not descriptor.enabled or descriptor.state in {"disabled", "not_connected", "reconnect_required"}:
            state = "disconnected"
        else:
            state = "ready"
        return {
            "provider": descriptor.id,
            "environment": descriptor.environment,
            "state": state,
            "message": descriptor.message,
        }
