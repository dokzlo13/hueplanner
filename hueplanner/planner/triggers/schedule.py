from __future__ import annotations

from dataclasses import dataclass
from datetime import time, timedelta

import structlog
from pydantic import BaseModel

from hueplanner.planner.actions import EvaluatedAction
from hueplanner.planner.serializable import Serializable
from hueplanner.scheduler import Scheduler
from .interface import PlanTrigger

logger = structlog.getLogger(__name__)


@dataclass
class PlanTriggerOnce(PlanTrigger, Serializable):
    act_on: str
    alias: str | None = None
    scheduler_tag: str | None = None

    class _Model(BaseModel):
        act_on: str
        alias: str | None = None
        scheduler_tag: str | None = None

    async def apply_trigger(self, action: EvaluatedAction, scheduler: Scheduler):
        logger.debug("Applying once trigger", act_on=str(self.act_on))
        alias = self.alias if self.alias is not None else self.act_on
        act_on_time = (await time_parser.parse(self.act_on)).timetz()
        await scheduler.once(
            action,
            act_on_time,
            alias=alias,
            tags={self.scheduler_tag} if self.scheduler_tag is not None else None,
        )


@dataclass
class PlanTriggerPeriodic(PlanTrigger, Serializable):
    interval: timedelta
    first_run_time: time | None = None
    alias: str | None = None

    class _Model(BaseModel):
        interval: timedelta
        first_run_time: time | None = None
        alias: str | None = None

    async def apply_trigger(self, action: EvaluatedAction, scheduler: Scheduler):
        logger.debug("Applying periodic trigger", interval=str(self.interval), first_run_time=str(self.first_run_time))
        await scheduler.cyclic(action, interval=self.interval, first_run_time=self.first_run_time, alias=self.alias)
