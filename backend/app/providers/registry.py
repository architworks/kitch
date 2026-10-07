"""Backend-owned grocery provider registry."""

from __future__ import annotations

import asyncio
from typing import Dict

from app.providers.base import (
    GroceryProviderAdapter,
    ProviderCapabilities,
    ProviderDescriptor,
    ProviderOperationError,
)
from app.providers.instamart import InstamartProviderAdapter
from app.providers.zepto import ZeptoProviderAdapter


PROVIDER_READINESS_TIMEOUT_SECONDS = 5.0


class ProviderRegistry:
    _ALIASES = {
        "zepto": "zepto",
        "swiggy": "swiggy_instamart",
        "instamart": "swiggy_instamart",
        "swiggy_instamart": "swiggy_instamart",
    }

    @classmethod
    def canonical_id(cls, provider_id: str) -> str:
        """Resolve user-facing provider names to Kitch's stable provider key."""
        normalized = "_".join(
            str(provider_id or "").strip().lower().replace("-", " ").split()
        )
        return cls._ALIASES.get(normalized, normalized)

    async def _readiness_for(
        self,
        adapter: GroceryProviderAdapter,
        descriptor: ProviderDescriptor,
    ) -> Dict[str, object]:
        if descriptor.production_gated or descriptor.state == "gated":
            return {
                "provider": descriptor.id,
                "environment": descriptor.environment,
                "state": "gated",
                "message": descriptor.message,
            }
        if not descriptor.enabled or descriptor.state in {
            "disabled",
            "not_connected",
            "reconnect_required",
        }:
            return {
                "provider": descriptor.id,
                "environment": descriptor.environment,
                "state": "disconnected",
                "message": descriptor.message,
            }
        return await asyncio.wait_for(
            adapter.readiness(),
            timeout=PROVIDER_READINESS_TIMEOUT_SECONDS,
        )

    def descriptors(self) -> list[Dict[str, object]]:
        instamart = InstamartProviderAdapter().descriptor()
        zepto = ZeptoProviderAdapter().descriptor()
        blinkit = ProviderDescriptor(
            id="blinkit",
            label="Blinkit",
            brand_label="blinkit",
            description="A future ordering option for the same reviewed native cart.",
            enabled=False,
            state="coming_soon",
            message="Blinkit support is coming soon.",
            badge="Coming soon",
            capabilities=ProviderCapabilities(),
            theme={"start": "#f5c400", "end": "#148447"},
        )
        return [instamart.as_dict(), zepto.as_dict(), blinkit.as_dict()]

    def get(self, provider_id: str) -> GroceryProviderAdapter:
        provider_id = self.canonical_id(provider_id)
        factories = {
            "zepto": ZeptoProviderAdapter,
            "swiggy_instamart": InstamartProviderAdapter,
        }
        factory = factories.get(provider_id)
        if not factory:
            raise ProviderOperationError(
                provider=provider_id,
                operation="resolve_provider",
                code="provider_not_available",
                message="The selected grocery provider is not available.",
                status_code=404,
            )
        adapter = factory()
        descriptor = adapter.descriptor()
        if not descriptor.enabled:
            raise ProviderOperationError(
                provider=provider_id,
                operation="resolve_provider",
                code="provider_not_available",
                message=descriptor.message,
                status_code=403 if descriptor.production_gated else 422,
            )
        return adapter

    def descriptor(self, provider_id: str) -> Dict[str, object]:
        provider_id = self.canonical_id(provider_id)
        for descriptor in self.descriptors():
            if descriptor["id"] == provider_id:
                return descriptor
        raise ProviderOperationError(
            provider=provider_id,
            operation="resolve_provider",
            code="provider_not_available",
            message="The selected grocery provider is not available.",
            status_code=404,
        )

    async def readiness(self) -> list[Dict[str, object]]:
        adapters = [ZeptoProviderAdapter(), InstamartProviderAdapter()]
        descriptors = await asyncio.gather(
            *(asyncio.to_thread(adapter.descriptor) for adapter in adapters)
        )
        results = await asyncio.gather(
            *(
                self._readiness_for(adapter, descriptor)
                for adapter, descriptor in zip(adapters, descriptors)
            ),
            return_exceptions=True,
        )
        readiness: list[Dict[str, object]] = []
        for descriptor, result in zip(descriptors, results):
            if isinstance(result, Exception):
                timed_out = isinstance(result, asyncio.TimeoutError)
                readiness.append({
                    "provider": descriptor.id,
                    "environment": descriptor.environment,
                    "state": "degraded" if descriptor.enabled else "disconnected",
                    "message": (
                        f"{descriptor.label} readiness timed out."
                        if timed_out
                        else f"{descriptor.label} readiness could not be verified."
                    ),
                })
            else:
                readiness.append(result)
        readiness.append({
            "provider": "blinkit",
            "environment": "production",
            "state": "disconnected",
            "message": "Blinkit support is coming soon.",
        })
        return readiness


provider_registry = ProviderRegistry()
