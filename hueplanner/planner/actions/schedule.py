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
    # Initially try to find tasks with valid `prev()` values
    valid_tasks = [task for task in tasks if task.schedule.prev() is not None]
    using_prev = True  # Flag to indicate if we're using `prev()`

    if not valid_tasks and overlap:
        # If no valid previous tasks and overlap is allowed, try using `next()` instead
        valid_tasks = [task for task in tasks if task.schedule.next() is not None]
        using_prev = False  # We are now using `next()` values

    if not valid_tasks:
        return None

    # Sort depending on whether we are using `prev()` or `next()`
    if using_prev:
        valid_tasks.sort(key=lambda t: t.schedule.prev(), reverse=True)  # Sort by `prev()` (most recent first)
    else:
        valid_tasks.sort(key=lambda t: t.schedule.next())  # Sort by `next()` (soonest first)

    return valid_tasks[0] if valid_tasks else None


def get_closest_next(tasks: tuple[SchedulerTask, ...], overlap: bool) -> SchedulerTask | None:
    # Initially try to find tasks with valid `next()` values
    valid_tasks = [task for task in tasks if task.schedule.next() is not None]
    using_next = True  # Flag to indicate if we're using `next()`

    if not valid_tasks and overlap:
        # If no valid next tasks and overlap is allowed, try using `prev()` instead
        valid_tasks = [task for task in tasks if task.schedule.prev() is not None]
        using_next = False  # We are now using `prev()` values

    if not valid_tasks:
        return None

    # Sort depending on whether we are using `next()` or `prev()`
    if using_next:
        valid_tasks.sort(key=lambda t: t.schedule.next())  # Sort by `next()` (soonest first)
    else:
        valid_tasks.sort(key=lambda t: t.schedule.prev(), reverse=True)  # Sort by `prev()` (most recent first)

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
            logger.info("Off-schedule task execution requested", action=repr(self))

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
            logger.info(
                "Found closest task, executing it at current time (off schedule)",
                task=closest_task,
                strategy=self.strategy.name,
            )
            await closest_task.execute()

        logger.info("Run task off-schedule action prepared", action=repr(self))

        return run_closest_schedule
