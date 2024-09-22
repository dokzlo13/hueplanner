# from ..interface import PlanAction, EvaluatedAction
from __future__ import annotations

from typing import Awaitable, Protocol


class EvaluatedCondition(Protocol):
    def __call__(self, *args, **kwargs) -> Awaitable[bool]: ...


class PlanCondition(Protocol):
    async def define_condition(self, *args, **kwargs) -> EvaluatedCondition: ...
