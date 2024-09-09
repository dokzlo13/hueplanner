from __future__ import annotations

from dataclasses import dataclass

import structlog

from hueplanner.planner.serializable import Serializable
from hueplanner.scheduler import Scheduler

from .interface import EvaluatedAction, PlanAction

logger = structlog.getLogger(__name__)


@dataclass(kw_only=True)
class PlanActionPrintSchedule(PlanAction, Serializable):
    async def define_action(self, scheduler: Scheduler) -> EvaluatedAction:
        async def action():
            # logger.info(f"Current schedule: \n{scheduler}")
            print(f"Current schedule: \n{scheduler}", flush=True)

        return action
