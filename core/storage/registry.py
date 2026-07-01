"""Storage provider registry."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Generic, TypeVar

T = TypeVar("T")


@dataclass
class StorageProvider(Generic[T]):
    name: str
    priority: int
    provider_type: str
    factory: object

    async def can_initialize(self) -> bool:
        method = getattr(self.factory, "can_initialize", None)
        if method is None:
            return True
        return bool(await method())

    async def initialize(self) -> T:
        method = getattr(self.factory, "initialize", None)
        if method is None:
            return self.factory  # type: ignore[return-value]
        return await method()


class StorageRegistry:
    def __init__(self) -> None:
        self._providers: list[StorageProvider] = []

    def register(self, provider: StorageProvider) -> None:
        self._providers.append(provider)
        self._providers.sort(key=lambda item: item.priority, reverse=True)

    async def resolve_first(self, provider_type: str) -> object:
        for provider in self._providers:
            if provider.provider_type != provider_type:
                continue
            if await provider.can_initialize():
                return await provider.initialize()
        raise RuntimeError(f"No {provider_type} provider could initialize")
