from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

import structlog
from pydantic import BaseModel

from hueplanner.planner.serializable import Serializable
from hueplanner.scheduler import Scheduler, SchedulerTask

from .interface import EvaluatedAction, PlanAction

logger = structlog.getLogger(__name__)


class ClosestScheduleRunStrategy(Enum):
    PREV = "PREV"
    NEXT = "NEXT"
    PREV_NEXT = "PREV_NEXT"
    NEXT_PREV = "NEXT_PREV"


def get_closest_prev(tasks: tuple[SchedulerTask, ...], overlap: bool) -> SchedulerTask | None:
    valid_tasks = [task for task in tasks if task.schedule.prev() is not None]

    if not valid_tasks and overlap:
        # If no valid tasks and overlap is allowed, consider all tasks
        valid_tasks = [task for task in tasks]

    if not valid_tasks:
        return None

    # Sort by the `prev()` datetime (most recent to least recent)
    valid_tasks.sort(key=lambda t: t.schedule.prev(), reverse=True)

    return valid_tasks[0] if valid_tasks else None


def get_closest_next(tasks: tuple[SchedulerTask, ...], overlap: bool) -> SchedulerTask | None:
    valid_tasks = [task for task in tasks if task.schedule.next() is not None]

    if not valid_tasks and overlap:
        # If no valid tasks and overlap is allowed, consider all tasks
        valid_tasks = [task for task in tasks]

    if not valid_tasks:
        return None

    # Sort by the `next()` datetime (soonest to latest)
    valid_tasks.sort(key=lambda t: t.schedule.next())

    return valid_tasks[0] if valid_tasks else None


def get_closest_next_prev(tasks: tuple[SchedulerTask, ...], overlap: bool) -> SchedulerTask | None:
    # Try to find the closest previous task
    prev_task = get_closest_next(tasks, overlap)
    if prev_task is not None:
        return prev_task

    # If no previous task, fallback to the closest next task
    return get_closest_prev(tasks, overlap)


def get_closest_prev_next(tasks: tuple[SchedulerTask, ...], overlap: bool) -> SchedulerTask | None:
    # Try to find the closest next task
    next_task = get_closest_prev(tasks, overlap)
    if next_task is not None:
        return next_task

    # If no next task, fallback to the closest previous task
    return get_closest_next(tasks, overlap)


STRATEGIES = {
    ClosestScheduleRunStrategy.PREV: get_closest_prev,
    ClosestScheduleRunStrategy.NEXT: get_closest_next,
    ClosestScheduleRunStrategy.PREV_NEXT: get_closest_prev_next,
    ClosestScheduleRunStrategy.NEXT_PREV: get_closest_next_prev,
}


@dataclass(kw_only=True)
class PlanActionRunClosestSchedule(PlanAction, Serializable):
    strategy: ClosestScheduleRunStrategy
    allow_overlap: bool = False
    scheduler_tags: set[str] | None = None

    class _Model(BaseModel):
        strategy: ClosestScheduleRunStrategy
        allow_overlap: bool = False
        scheduler_tags: set[str] | None = None

    async def define_action(self) -> EvaluatedAction:
        strategy = STRATEGIES[self.strategy]

        async def run_closest_schedule(scheduler: Scheduler):
            all_tasks = scheduler.get_schedule()
            tasks = []

            for task in all_tasks:
                if self.scheduler_tags is None:
                    tasks.append(task)
                    continue
                # Check if the task's tags match
                if len(task.tags) and task.tags.issubset(self.scheduler_tags):
                    tasks.append(task)

            closest_task = strategy(tuple(tasks), overlap=self.allow_overlap)
            if not closest_task:
                logger.warning("No closest task found based on strategy", strategy=self.strategy.name)
                return
            logger.debug(
                "Found closest task, executing it at current time (off schedule)",
                task=closest_task,
                strategy=self.strategy.name,
            )
            await closest_task.execute()

        return run_closest_schedule
