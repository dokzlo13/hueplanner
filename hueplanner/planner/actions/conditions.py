from __future__ import annotations

import inspect
from typing import Awaitable, Callable

import structlog

from hueplanner.ioc import IOC

from .interface import EvaluatedAction, PlanAction

logger = structlog.getLogger(__name__)


class PlanActionWithEvaluationCondition(PlanAction):
    def __init__(self, condition: Callable[[], bool] | Callable[[], Awaitable[bool]], action: PlanAction) -> None:
        super().__init__()
        self._action: PlanAction = action
        self._condition = condition

    async def define_action(self, ioc: IOC) -> EvaluatedAction:
        async def _action():
            logger.info("Empty action executed (evaluation condition not match)")

        if inspect.iscoroutinefunction(self._condition):
            satisfied = await self._condition()  # Await if it's awaitable
        else:
            satisfied = self._condition()  # Call directly if it's not awaitable

        if satisfied:
            _action = await ioc.make(self._action.define_action)  # type: ignore
        else:
            logger.info("Action not evaluated because evaluation condition not match")

        return _action


class PlanActionWithRuntimeCondition(PlanAction):
    def __init__(self, condition: Callable[[], bool] | Callable[[], Awaitable[bool]], action: PlanAction) -> None:
        super().__init__()
        self._action: PlanAction = action
        self._condition = condition

    async def define_action(self, ioc: IOC) -> EvaluatedAction:
        _action = await ioc.make(self._action.define_action)

        async def action():
            if inspect.iscoroutinefunction(self._condition):
                satisfied = await self._condition()  # Await if it's awaitable
            else:
                satisfied = self._condition()  # Call directly if it's not awaitable

            if satisfied:
                return await _action()
            else:
                logger.info("Action not executed because runtime condition not match")

        return action
