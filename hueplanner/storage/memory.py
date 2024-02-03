from typing import AsyncContextManager, Dict, Generic, Hashable, TypeVar

from .interface import IKeyValueCollection, IKeyValueStorage

K = TypeVar("K", bound=Hashable)
V = TypeVar("V")


class InMemoryKeyValueStorage(IKeyValueStorage):
    def __init__(self, path: str):
        self.collections: Dict[str, InMemoryKeyValueCollection] = {}

    async def open(self, path: str) -> AsyncContextManager:
        # For in-memory storage, the path is irrelevant
        return self

    async def close(self) -> None:
        # Clear all collections to mimic closing a connection
        self.collections.clear()

    async def create_collection(self, name: str) -> "InMemoryKeyValueCollection":
        if name in self.collections:
            raise Exception(f"Collection {name} already exists.")
        self.collections[name] = InMemoryKeyValueCollection()
        return self.collections[name]

    async def delete_collection(self, name: str) -> bool:
        if name in self.collections:
            del self.collections[name]
            return True
        return False

    async def __aenter__(self):
        # No special actions needed to enter context
        return self

    async def __aexit__(self, exc_type, exc, tb):
        # Clear all collections on exit
        self.collections.clear()


class InMemoryKeyValueCollection(IKeyValueCollection[K, V], Generic[K, V]):
    def __init__(self):
        self.store: Dict[K, V] = {}

    async def contains(self, key: K) -> bool:
        return key in self.store

    async def set(self, key: K, value: V) -> None:
        self.store[key] = value

    async def get(self, key: K, default: V | None = None) -> V | None:
        return self.store.get(key, default)

    async def pop(self, key: K, default: V | None = None) -> V | None:
        return self.store.pop(key, default)

    async def delete(self, key: K) -> None:
        if key in self.store:
            del self.store[key]

    async def items(self) -> tuple[tuple[K, V], ...]:
        return tuple(self.store.items())

    async def delete_all(self) -> None:
        self.store.clear()

