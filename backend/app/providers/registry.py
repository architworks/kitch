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


class ProviderRegistry:
    def descriptors(self) -> list[Dict[str, object]]:
        zepto = ZeptoProviderAdapter().descriptor()
        instamart = InstamartProviderAdapter().descriptor()
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
        return [zepto.as_dict(), instamart.as_dict(), blinkit.as_dict()]

    def get(self, provider_id: str) -> GroceryProviderAdapter:
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
        results = await asyncio.gather(
            *(adapter.readiness() for adapter in adapters),
            return_exceptions=True,
        )
        readiness: list[Dict[str, object]] = []
        for adapter, result in zip(adapters, results):
            descriptor = adapter.descriptor()
            if isinstance(result, Exception):
                readiness.append({
                    "provider": descriptor.id,
                    "environment": descriptor.environment,
                    "state": "degraded" if descriptor.enabled else "disconnected",
                    "message": f"{descriptor.label} readiness could not be verified.",
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
