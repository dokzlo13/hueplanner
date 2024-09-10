from dataclasses import dataclass

from hueplanner.ioc import IOC

from .actions import PlanAction
from .triggers import PlanTrigger


@dataclass
class PlanEntry:
    trigger: PlanTrigger
    action: PlanAction

    async def apply(self, ioc: IOC):
        action = await ioc.make(self.action.define_action)
        await ioc.make(self.trigger.apply_trigger, ioc.inject(action))


Plan = list[PlanEntry]


class Planner:
    def __init__(self, ioc: IOC) -> None:
        self.ioc = ioc

    async def apply_plan(self, plan: Plan):
        for plan_entry in plan:
            await plan_entry.apply(self.ioc)
