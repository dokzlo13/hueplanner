from __future__ import annotations

import asyncio
from dataclasses import dataclass

import structlog
from pydantic import BaseModel

from hueplanner.event_listener import HueEventStreamListener
from hueplanner.ioc import IOC
from hueplanner.planner.serializable import Serializable
from hueplanner.scheduler import Scheduler

from ..planner import Plan, Planner  # to prevent circular import
from .interface import EvaluatedAction, PlanAction

logger = structlog.getLogger(__name__)


@dataclass(kw_only=True)
class PlanActionReEvaluatePlan(PlanAction, Serializable):
    reset_schedule: bool = False
    reset_event_listeners: bool = False

    class _Model(BaseModel):
        reset_schedule: bool = False
        reset_event_listeners: bool = False

    async def define_action(self) -> EvaluatedAction:

        async def action(
            event_listener: HueEventStreamListener | None,
            ioc: IOC,
            plan: Plan,
            scheduler: Scheduler,
        ):
            logger.warning("Plan re-evaluation requested", action=repr(self))

            if self.reset_event_listeners:
                if event_listener is not None:
                    logger.info("Resetting HUE EventListener callbacks")
                    event_listener.clean_callbacks()
                    logger.info("HUE Event Listener callbacks reset")

            if self.reset_schedule:
                logger.info("Resetting Schedule")
                await scheduler.reset()
                logger.info("Schedule reset performed")
                await asyncio.sleep(1)

            logger.info("Applying new plan...")
            await Planner(ioc).apply_plan(plan)

            logger.warning("Plan re-evaluated")

        return action
