from __future__ import annotations

import structlog

from hueplanner.ioc import IOC
from hueplanner.planner.conditions import PlanCondition

from .interface import EvaluatedAction, PlanAction

logger = structlog.getLogger(__name__)


class PlanActionRunIf(PlanAction):
    def __init__(self, condition: PlanCondition, action: PlanAction) -> None:
        super().__init__()
        self._action = action
        self._condition = condition

    async def define_action(self, ioc: IOC) -> EvaluatedAction:
        _action = await ioc.make(self._action.define_action)
        _condition = await ioc.make(self._condition.define_condition)

        async def action():
            satisfied = await ioc.make(_condition)
            if satisfied:
                logger.info("Runtime condition met, executing action", condition=self._condition)
                return await ioc.make(_action)
            else:
                logger.info("Runtime condition is NOT met, action not executed", condition=self._condition)

        return action
