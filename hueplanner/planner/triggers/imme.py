from __future__ import annotations

from dataclasses import dataclass

import structlog

from hueplanner.planner.actions import EvaluatedAction
from hueplanner.planner.serializable import Serializable

from .interface import PlanTrigger

logger = structlog.getLogger(__name__)


@dataclass
class PlanTriggerImmediately(PlanTrigger, Serializable):
    async def apply_trigger(self, action: EvaluatedAction):
        logger.info(f"Executing action immediately: {action}")
        await action()
