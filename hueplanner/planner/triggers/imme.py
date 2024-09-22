from __future__ import annotations

import structlog
from pydantic.dataclasses import dataclass

from hueplanner.planner.actions import EvaluatedAction
from hueplanner.planner.serializable import Serializable

from .interface import PlanTrigger

logger = structlog.getLogger(__name__)


@dataclass
class PlanTriggerImmediately(PlanTrigger, Serializable):
    async def apply_trigger(self, action: EvaluatedAction):
        logger.info("Executing action immediately", action=action, trigger=repr(self))
        await action()
