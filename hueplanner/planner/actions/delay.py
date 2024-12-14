from __future__ import annotations

import asyncio

import structlog

from hueplanner.ioc import IOC

from .interface import EvaluatedAction, PlanAction

logger = structlog.getLogger(__name__)


class PlanActionDelayed(PlanAction):
    def __init__(self, delay: float, action: PlanAction) -> None:
        super().__init__()
        self._action = action
        self._delay = delay

    async def define_action(self, ioc: IOC) -> EvaluatedAction:
        _action = await ioc.make(self._action.define_action)

        async def action():
            logger.info(f"Awaiting for delay: {self._delay:.4f}s.")
            await asyncio.sleep(delay=self._delay)
            logger.info("Executing action")
            return await ioc.make(_action)

        return action
