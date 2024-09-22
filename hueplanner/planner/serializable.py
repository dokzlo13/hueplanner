from typing import Any, Protocol

from pydantic import TypeAdapter


class Serializable(Protocol):
    @classmethod
    def loads(cls, data: dict[str, Any]):
        return TypeAdapter(cls).validate_python(data)

    def dumps(self) -> dict[str, Any]:
        return TypeAdapter(self.__class__).dump_python(self)
