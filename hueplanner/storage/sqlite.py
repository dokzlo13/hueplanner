import aiosqlite
import pickle
import hashlib
from typing import Callable, TypeVar, Generic, Hashable
from .interface import IKeyValueStorage, IKeyValueCollection

K = TypeVar("K", bound=Hashable)
V = TypeVar("V")


def _table_name(name: str) -> str:
    return f"kv_{name}"


class SqliteKeyValueStorage(IKeyValueStorage):
    """
    async with KeyValueStorage("./db.sqlite") as storage:
        my_data = await storage.create_collection("somedata")
        await my_data.set('Key', {"hello": "world"})
        print(list(await my_data.items()))

    storage = await KeyValueStorage.open("./db.sqlite")
    ...
    await storage.close()
    """

    def __init__(self, path: str):
        self._db = None
        self._path = path

    @classmethod
    async def open(cls, path: str):
        self = cls(path)
        await self._open()
        return self

    async def _open(self):
        self._db = await aiosqlite.connect(self._path)
        await self._db.execute("PRAGMA foreign_keys = ON")

    async def close(self):
        if self._db is not None:
            await self._db.commit()  # Ensure all transactions are committed.
            await self._db.close()
            self._db = None

    async def __aenter__(self):
        if self._db is None:
            await self._open()
        return self

    async def __aexit__(self, exc_type, exc, tb):
        await self.close()

    @property
    def db(self) -> aiosqlite.Connection:
        if self._db is None:
            raise Exception("Database connection is not open. Please call open() before any operations.")
        return self._db

    def get_db_connection(self) -> aiosqlite.Connection:
        return self.db  # Use the property to leverage the built-in error handling

    async def create_collection(self, name: str) -> "SqliteKeyValueCollection":
        table_name = _table_name(name)
        await self.db.execute(
            f"""
            CREATE TABLE IF NOT EXISTS {table_name} (
                hash TEXT PRIMARY KEY,
                key BLOB NOT NULL,
                value BLOB NOT NULL
            )
        """
        )
        # Verify schema
        cursor = await self.db.execute(f"PRAGMA table_info({table_name})")
        columns = await cursor.fetchall()
        expected_columns = [("hash", "TEXT"), ("key", "BLOB"), ("value", "BLOB")]
        if not all(col[1] == exp[0] and col[2].startswith(exp[1]) for col, exp in zip(columns, expected_columns)):
            raise Exception(f"Table {table_name!r} exists but has an incorrect schema.")
        await self.db.commit()
        return SqliteKeyValueCollection(self.get_db_connection, name)

    async def delete_collection(self, name: str) -> bool:
        table_name = _table_name(name)
        try:
            await self.db.execute(f"DROP TABLE IF EXISTS {table_name}")
            await self.db.commit()
            return True
        except Exception:
            return False


class SqliteKeyValueCollection(IKeyValueCollection[K, V], Generic[K, V]):
    def __init__(self, db_connection_callback: Callable[[], aiosqlite.Connection], name: str):
        self._name = name
        self._table_name = _table_name(name)
        self.db_connection_callback = db_connection_callback

    @property
    def name(self) -> str:
        return self._name

    @property
    def db(self) -> aiosqlite.Connection:
        return self.db_connection_callback()

    async def contains(self, key: K) -> bool:
        key_hash = self._compute_hash(key)
        async with self.db.execute(f"SELECT 1 FROM {self._table_name} WHERE hash = ?", (key_hash,)) as cursor:
            return await cursor.fetchone() is not None

    async def set(self, key: K, value: V) -> None:
        key_blob = self._serialize_data(key)
        value_blob = self._serialize_data(value)
        key_hash = self._compute_hash(key)
        await self.db.execute(
            f"REPLACE INTO {self._table_name} (hash, key, value) VALUES (?, ?, ?)", (key_hash, key_blob, value_blob)
        )
        await self.db.commit()

    async def get(self, key: K, default: V | None = None) -> V | None:
        key_hash = self._compute_hash(key)
        async with self.db.execute(f"SELECT value FROM {self._table_name} WHERE hash = ?", (key_hash,)) as cursor:
            row = await cursor.fetchone()
            if row:
                return self._deserialize_data(row[0])
            else:
                return default

    async def pop(self, key: K, default: V | None = None) -> V | None:
        value = await self.get(key, default)
        await self.delete(key)
        return value

    async def delete(self, key: K) -> None:
        key_hash = self._compute_hash(key)
        await self.db.execute(f"DELETE FROM {self._table_name} WHERE hash = ?", (key_hash,))
        await self.db.commit()

    async def delete_all(self) -> None:
        await self.db.execute(f"DELETE FROM {self._table_name}")
        await self.db.commit()

    async def items(self) -> tuple[tuple[K, V], ...]:
        items_list = []
        async with self.db.execute(f"SELECT key, value FROM {self._table_name}") as cursor:
            rows = await cursor.fetchall()
            for row in rows:
                key = self._deserialize_data(row[0])
                value = self._deserialize_data(row[1])
                items_list.append((key, value))
        return tuple(items_list)

    async def size(self) -> int:
        async with self.db.execute(f"SELECT COUNT(key) FROM {self._table_name}") as cursor:
            row = await cursor.fetchone()
            if not row:
                raise ValueError("Failed to count entires")
            return row[0]

    def _compute_hash(self, key: K) -> str:
        key_blob = self._serialize_data(key)
        return hashlib.sha256(key_blob).hexdigest()

    def _serialize_data(self, data) -> bytes:
        return pickle.dumps(data)

    def _deserialize_data(self, data: bytes):
        return pickle.loads(data)


async def main():
    async with SqliteKeyValueStorage("./db.sqlite") as storage:
        my_data = await storage.create_collection("somedata")
        await my_data.set((1, 2, 3), "thisismydata")
        await my_data.set("Key", {"hello": "world"})
        print(list(await my_data.items()))
        await storage.delete_collection("somedata")


if __name__ == "__main__":
    import asyncio

    loop = asyncio.get_event_loop()
    loop.run_until_complete(main())
