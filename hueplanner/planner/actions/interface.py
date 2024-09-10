from __future__ import annotations

from typing import Awaitable, Protocol, Callable

import structlog


logger = structlog.getLogger(__name__)

# - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -


class EvaluatedAction(Protocol):
    def __call__(self, *args, **kwargs) -> Awaitable[None]: ...


class PlanAction(Protocol):
    async def define_action(self, *args, **kwargs) -> EvaluatedAction: ...

    # def chain(self, other: PlanAction) -> PlanAction:
    #     return PlanActionSequence(self, other)

    # def if_(self, cond: Callable[[], bool] | Callable[[], Awaitable[bool]]) -> PlanAction:
    #     return PlanActionWithRuntimeCondition(cond, self)

    # def with_callback(
    #     self, callback: Callable[..., None] | Callable[..., Awaitable[None]], *args, **kwargs
    # ) -> PlanAction:
    #     return PlanActionSequence(self, PlanActionCallback(callback, *args, **kwargs))
