from dataclasses import dataclass

from .actions import PlanAction
from .context import Context
from .triggers import PlanTrigger


@dataclass
class PlanEntry:
    trigger: PlanTrigger
    action: PlanAction

    async def apply(self, context: Context):
        action = await self.action.define_action(context)
        await self.trigger.apply_trigger(context, action)


class Planner:
    def __init__(self, context: Context) -> None:
        self.context = context

    async def apply_plan(self, plan: list[PlanEntry]):
        for plan_entry in plan:
            await plan_entry.apply(self.context)
