from __future__ import annotations

from typing import Protocol

from hueplanner.planner.actions import EvaluatedAction

# - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -


class PlanTrigger(Protocol):

    async def apply_trigger(self, action: EvaluatedAction, *args, **kwargs): ...
