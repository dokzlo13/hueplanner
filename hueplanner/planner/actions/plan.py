from __future__ import annotations

import asyncio
from dataclasses import dataclass

import structlog
from pydantic import BaseModel

from hueplanner.ioc import IOC
from hueplanner.planner.serializable import Serializable
from hueplanner.scheduler import Scheduler

from ..planner import Plan, Planner  # to prevent circular import
from .interface import EvaluatedAction, PlanAction

logger = structlog.getLogger(__name__)


@dataclass(kw_only=True)
class PlanActionReEvaluatePlan(PlanAction, Serializable):
    reset_schedule: bool

    class _Model(BaseModel):
        reset_schedule: bool = True

    async def define_action(self, ioc: IOC, plan: Plan, scheduler: Scheduler) -> EvaluatedAction:
        async def action():
            logger.warning("Performing plan re-evaluation")

            if self.reset_schedule:
                logger.warning("Resetting Schedule")
                await scheduler.reset()
                logger.warning("Schedule reset performed")
                await asyncio.sleep(1)

            await Planner(ioc).apply_plan(plan)
            logger.warning("Plan re-evaluated")

        return action
