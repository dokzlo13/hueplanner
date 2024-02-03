from __future__ import annotations

from typing import AsyncContextManager, Hashable, Protocol, TypeVar

K = TypeVar("K", bound=Hashable)
V = TypeVar("V")


class IKeyValueStorage(Protocol):
    async def open(self, path: str) -> AsyncContextManager:
        ...

    async def close(self) -> None:
        ...

    async def create_collection(self, name: str) -> IKeyValueCollection:
        ...

    async def delete_collection(self, name: str) -> bool:
        ...


class IKeyValueCollection(Protocol[K, V]):
    async def contains(self, key: K) -> bool:
        ...

    async def set(self, key: K, value: V) -> None:
        ...

    async def get(self, key: K, default: V | None = None) -> V | None:
        ...

    async def pop(self, key: K, default: V | None = None) -> V | None:
        ...

    async def delete(self, key: K) -> None:
        ...

    async def items(self) -> tuple[tuple[K, V], ...]:
        ...
