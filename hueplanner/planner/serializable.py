from typing import Any, Protocol

from pydantic import BaseModel


class Serializable(Protocol):
    @property
    def _Model(self) -> BaseModel: ...

    @classmethod
    def loads(cls, data: dict[str, Any]):
        return cls(**cls._Model.model_validate(data).model_dump())  # type: ignore

    def dumps(self) -> dict[str, Any]:
        return self._Model.model_validate(self, from_attributes=True).model_dump()
