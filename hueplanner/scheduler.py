from __future__ import annotations

import asyncio
import random
from abc import abstractmethod
from contextlib import suppress
from datetime import datetime, time, timedelta, tzinfo
from functools import total_ordering
from typing import Awaitable, Callable, Protocol, runtime_checkable

import structlog

# Setup structlog for structured logging
logger = structlog.getLogger(__name__)


Task = Callable[[], Awaitable[None]]


def str_cutoff(text: str, max_width: int | None = None) -> str:
    """Cuts off the string to fit the max_width with '...' appended if truncated."""
    if max_width is None:
        return text
    return text if len(text) <= max_width else text[: max_width - 3] + "..."


# @runtime_checkable
# class Wrapper(Protocol):
#     @abstractmethod
#     async def execute(self, *args, **kwargs):
#         pass

#     def __call__(self, *args, **kwargs) -> Awaitable[None]:
#         return self.execute(*args, **kwargs)

#     def get_task_name(self):
#         # Recursively get the name or repr of the task being executed
#         func = getattr(self, "func", None)
#         if isinstance(func, Wrapper):
#             return repr(func)
#         elif hasattr(func, "__name__"):
#             return f"<{func.__name__}>"  # Return the function name if available
#         else:
#             return repr(func)  # Fallback to repr for other callable objects

#     def __repr__(self):
#         # Return a simple class name representation if no specific function is wrapped
#         return f"{self.__class__.__name__}({self.get_task_name()})"


# class ReliableWrapper(Wrapper):
#     def __init__(
#         self, func: Callable[..., Awaitable[None]], max_retries=3, base_backoff=1, handle_exceptions=(Exception,)
#     ):
#         self.func = func
#         self.max_retries = max_retries
#         self.base_backoff = base_backoff
#         self.handle_exceptions = handle_exceptions

#     async def execute(self, *args, **kwargs):
#         log = logger.bind(task=repr(self.func))
#         attempt = 0
#         while attempt < self.max_retries:
#             try:
#                 # log.debug("Starting task with retries", attempt=attempt + 1, max_retries=self.max_retries)
#                 # Execute the function with provided args and kwargs
#                 result = await self.func(*args, **kwargs)
#                 # log.debug("Task completed successfully", attempt=attempt + 1)
#                 return result
#             except self.handle_exceptions as e:
#                 attempt += 1
#                 log.exception("Task raised an exception, retrying", attempt=attempt, exception=str(e))
#                 backoff = self._get_backoff_time(attempt)
#                 if attempt >= self.max_retries:
#                     log.error("Max retries reached, task failed", attempt=attempt)
#                     break
#                 log.info("Retrying after backoff", attempt=attempt, backoff=round(backoff, 3))
#                 await asyncio.sleep(backoff)
#         log.error("Task failed after all retries")
#         return None

#     def _get_backoff_time(self, attempt):
#         backoff = self.base_backoff * (2 ** (attempt - 1))
#         jitter = random.uniform(0, backoff * 0.1)
#         return backoff + jitter


# class TimeoutWrapper(Wrapper):
#     def __init__(self, func: Callable[..., Awaitable[None]], run_until: datetime, tz: tzinfo | None = None):
#         self.func = func
#         self.run_until = run_until
#         self.tz = tz

#     async def execute(self, *args, **kwargs):
#         log = logger.bind(task=repr(self.func))
#         time_left = (self.run_until - datetime.now(self.tz)).total_seconds()
#         if time_left <= 0:
#             log.warning("Task cancelled due to run_until time exceeded")
#             return None  # Task cancelled silently
#         try:
#             # log.debug("Starting task with timeout", timeout=time_left)
#             return await asyncio.wait_for(self.func(*args, **kwargs), timeout=time_left)
#         except asyncio.TimeoutError:
#             log.warning("Task timed out and was cancelled")
#             return None  # Silent cancellation


# class StopCancellationWrapper(Wrapper):
#     def __init__(self, func: Callable[..., Awaitable[None]], stop_event: asyncio.Event):
#         self.func = func
#         self.stop_event = stop_event

#     async def execute(self, *args, **kwargs):
#         log = logger.bind(task=repr(self.func))

#         # log.debug("Starting task with stop event cancellation", stop_event=self.stop_event)

#         stop_task = asyncio.create_task(self.stop_event.wait())
#         wrapped_task = asyncio.create_task(self.func(*args, **kwargs))

#         done, pending = await asyncio.wait([stop_task, wrapped_task], return_when=asyncio.FIRST_COMPLETED)

#         if stop_task in done:
#             log.warning("Task cancelled due to stop_event trigger")
#             wrapped_task.cancel()
#             try:
#                 await wrapped_task  # Ensure is cancelled
#                 return
#             except asyncio.CancelledError:
#                 log.error("Wrapped task was cancelled")
#                 return None

#         # if wrapped_task not in done:
#         # log.debug("Task was cancelled")
#         return await wrapped_task if wrapped_task in done else None


@total_ordering
class ScheduleEntry(Protocol):
    def next_many(self, n: int = 1, pivot: datetime | None = None) -> tuple[datetime, ...]: ...

    def prev_many(self, n: int = 1, pivot: datetime | None = None) -> tuple[datetime, ...]: ...

    def next(self, pivot: datetime | None = None) -> datetime | None:
        runs = self.next_many(n=1, pivot=pivot)
        if not len(runs):
            return None
        return runs[0]

    def prev(self, pivot: datetime | None = None) -> datetime | None:
        runs = self.prev_many(n=1, pivot=pivot)
        if not len(runs):
            return None
        return runs[0]

    # def __eq__(self, other: object) -> bool:
    #     if type(self) is not type(other):
    #         return False
    #     return self.next_many(5) == other.next_many(5)

    def __eq__(self, other: object) -> bool:
        if type(self) is not type(other):
            return False
        return hash(self) == hash(other)

    def __lt__(self, other: "ScheduleEntry"):
        mine, others = self.next(), other.next()
        if mine is None:
            return True
        if others is None:
            return False
        return mine < others


class ScheduleOnce(ScheduleEntry):
    def __init__(
        self,
        run_at: time | None = None,
        tz: tzinfo | None = None,
    ) -> None:
        self.tz = tz
        self.run_at = run_at if run_at else datetime.now(tz=self.tz).time()

    def __repr__(self) -> str:
        s = f"{self.__class__.__name__}(run_at={self.run_at}"
        if self.tz is not None:
            s += f", tz={self.tz}"
        s += ")"
        return s

    def __hash__(self) -> int:
        return hash(("once", self.run_at, self.tz))

    def next_many(self, n: int = 1, pivot: datetime | None = None) -> tuple[datetime, ...]:
        """Return the next execution time if it hasn't happened yet."""
        if pivot is None:
            pivot = datetime.now(tz=self.tz)

        # Calculate the exact scheduled time
        scheduled_time = datetime.combine(pivot.date(), self.run_at, tzinfo=self.tz)

        # If the scheduled time is in the past, return an empty tuple
        if scheduled_time <= pivot:
            return ()

        return (scheduled_time,)  # Task happens once in the future

    def prev_many(self, n: int = 1, pivot: datetime | None = None) -> tuple[datetime, ...]:
        """Return the previous execution time if it has already happened."""
        if pivot is None:
            pivot = datetime.now(tz=self.tz)

        # Calculate the exact scheduled time
        scheduled_time = datetime.combine(pivot.date(), self.run_at, tzinfo=self.tz)

        # If the task is still in the future, return an empty tuple
        if scheduled_time > pivot:
            return ()

        return (scheduled_time,)  # Task has already happened


class SchedulePeriodic(ScheduleEntry):
    def __init__(
        self,
        interval: timedelta,
        start_at: time | None = None,
        tz: tzinfo | None = None,
    ) -> None:
        self.interval = interval
        self.tz = tz
        self.start_at = start_at if start_at else datetime.now(tz=self.tz).time()

    def __repr__(self) -> str:
        s = f"{self.__class__.__name__}(start_at={self.start_at}, interval={self.interval}"
        if self.tz is not None:
            s += f", tz={self.tz}"
        s += ")"
        return s

    def __hash__(self) -> int:
        return hash(("periodic", self.start_at, self.interval, self.tz))

    def next_many(self, n: int = 1, pivot: datetime | None = None) -> tuple[datetime, ...]:
        """Return the next `n` execution times after the `pivot` time."""
        if pivot is None:
            pivot = datetime.now(tz=self.tz)

        # Calculate the first task execution after the pivot
        first_execution = datetime.combine(pivot.date(), self.start_at, tzinfo=self.tz)
        if first_execution < pivot:
            # Move the first execution time forward by intervals until it's after the pivot
            delta_since_start = (pivot - first_execution).total_seconds()
            intervals_since_start = (delta_since_start // self.interval.total_seconds()) + 1
            first_execution += timedelta(seconds=intervals_since_start * self.interval.total_seconds())

        result = []
        current_time = first_execution
        for _ in range(n):
            result.append(current_time)
            current_time += self.interval  # Increment by the interval

        return tuple(result)

    def prev_many(self, n: int = 1, pivot: datetime | None = None) -> tuple[datetime, ...]:
        """Return the previous `n` execution times before the `pivot` time."""
        if pivot is None:
            pivot = datetime.now(tz=self.tz)

        # Calculate the first task execution on or before the pivot
        first_execution = datetime.combine(pivot.date(), self.start_at, tzinfo=self.tz)

        # If first_execution is after pivot, move it back to the previous day if necessary
        if first_execution > pivot:
            first_execution -= timedelta(days=1)

        # Calculate how many intervals have passed from first_execution to pivot
        delta_since_start = (pivot - first_execution).total_seconds()
        intervals_since_start = delta_since_start // self.interval.total_seconds()

        # Compute the most recent execution time before the pivot
        last_execution = first_execution + timedelta(seconds=intervals_since_start * self.interval.total_seconds())

        # Ensure last_execution is before the pivot
        if last_execution > pivot:
            last_execution -= self.interval

        result = []
        current_time = last_execution
        for _ in range(n):
            result.append(current_time)
            current_time -= self.interval  # Decrement by interval

        return tuple(result)


class AliasGenerator:
    def __init__(self):
        self.alias_counts = {}

    def generate_alias(self, alias: str) -> str:
        if alias in self.alias_counts:
            self.alias_counts[alias] += 1
            return f"{alias}_{self.alias_counts[alias]}"
        else:
            self.alias_counts[alias] = 1
            return alias

    def reset(self):
        self.alias_counts = {}


class SchedulerTask:
    def __init__(
        self,
        schedule: ScheduleEntry,
        coro: Task,
        alias: str,
        tags: set[str],
        tz: tzinfo | None = None,
    ) -> None:
        self.schedule = schedule
        self.coro = coro

        self.alias = alias
        self.tags = tags
        self.tz = tz

    def __repr__(self) -> str:
        s = (
            f"{self.__class__.__name__}(schedule={self.schedule!r}, coro={self.coro!r}, "
            f"alias={self.alias!r}, tags={self.tags}"
        )
        if self.tz is not None:
            s += f", tz={self.tz}"
        s += ")"
        return s

    def __eq__(self, value: object) -> bool:
        if not isinstance(value, self.__class__):
            raise TypeError(f"could not compare {self.__class__} and {value.__class__}")
        return (
            self.schedule == value.schedule
            and self.coro is value.coro
            and self.alias == value.alias
            and self.tags == value.tags
            and self.tz == value.tz
        )

    async def run(self, stop_event: asyncio.Event):
        while not stop_event.is_set() and (next_run := self.schedule.next()) is not None:
            seconds_until_next_run = (next_run - datetime.now(self.tz)).total_seconds()

            with suppress(asyncio.TimeoutError):
                await asyncio.wait_for(stop_event.wait(), timeout=seconds_until_next_run)
                return

            await self.coro()

    async def execute(self):
        return await self.coro()


class Scheduler:
    def __init__(self, tz: tzinfo | None = None) -> None:
        self.tz = tz
        self.alias_generator = AliasGenerator()

        self.pending_tasks: asyncio.Queue[SchedulerTask] = asyncio.Queue()
        # self.active_aio_tasks: set[asyncio.Task] = set()

        self._tasks: dict[asyncio.Task, SchedulerTask] = {}
        # self._task_lock = asyncio.Lock()

    def _make_alias(self, coro: Task, alias: str | None) -> str:
        alias = alias or coro.__name__
        return self.alias_generator.generate_alias(alias)

    def _schedule(self, task: SchedulerTask):
        logger.debug("task added to pending tasks", task=task)
        self.pending_tasks.put_nowait(task)

    def periodic(
        self,
        coro: Task,
        interval: timedelta,
        start_at: time | None = None,
        alias: str | None = None,
        tags: set[str] | None = None,
    ):
        task = SchedulerTask(
            schedule=SchedulePeriodic(interval=interval, start_at=start_at, tz=self.tz),
            coro=coro,
            alias=self._make_alias(coro, alias),
            tags=tags or set(),
            tz=self.tz,
        )
        self._schedule(task)

    def once(
        self,
        coro: Task,
        run_at: time,
        alias: str | None = None,
        tags: set[str] | None = None,
    ):
        task = SchedulerTask(
            schedule=ScheduleOnce(run_at=run_at, tz=self.tz),
            coro=coro,
            alias=self._make_alias(coro, alias),
            tags=tags or set(),
            tz=self.tz,
        )
        self._schedule(task)

    async def run(self, stop_event: asyncio.Event, exit_on_empty_schedule: bool = False):
        logger.info("Starting scheduler")

        while not stop_event.is_set():
            while not self.pending_tasks.empty():
                try:
                    scheduler_task = await asyncio.wait_for(self.pending_tasks.get(), 1.0)
                except asyncio.TimeoutError:
                    continue

                self.pending_tasks.task_done()
                logger.debug("Scheduled a task", task=scheduler_task)
                aio_task = asyncio.create_task(scheduler_task.run(stop_event))
                self._tasks[aio_task] = scheduler_task

            for aio_task, scheduler_task in self._tasks.copy().items():
                if aio_task.done():
                    if not aio_task.cancelled():
                        # get the exception raised by a task
                        if exception := aio_task.exception():
                            try:
                                raise exception
                            except Exception:
                                logger.exception("Exception in the managed task:", task=scheduler_task)
                                # raise

                    logger.debug("Task unscheduled", task=scheduler_task, aio_task=aio_task)
                    del self._tasks[aio_task]

            if exit_on_empty_schedule and not self._tasks:
                break

            with suppress(asyncio.TimeoutError):
                await asyncio.wait_for(stop_event.wait(), 1.0)
                logger.warning("Stop signal received")
                break

        logger.warning("Terminating scheduler")
        await self._shutdown_tasks()
        logger.info("Scheduler terminated")

    async def _shutdown_tasks(self):
        # If tasks not exited gracefully, terminate them by cancelling
        logger.debug("Shutting down tasks")
        active_tasks = self._tasks.copy()

        tasks = tuple(active_tasks.items())

        for aio_task, scheduler_task in tasks:
            # TODO: WHAT TO DO WITH IT??
            # if asyncio.current_task() is aio_task:
            #     logger.warning(f"Current task {aio_task.get_name()} tries to cancel itself")
            #     continue

            if not aio_task.done():
                aio_task.cancel()
            else:
                logger.debug(f"Task {aio_task.get_name()!r} exited", task=scheduler_task)

        for aio_task, scheduler_task in tasks:
            # TODO: WHAT TO DO WITH IT??
            # if asyncio.current_task() is aio_task:
            #     continue

            try:
                await aio_task
                logger.debug(f"Task {aio_task.get_name()!r} exited", task=scheduler_task)

            except asyncio.CancelledError:
                logger.debug(f"Task {aio_task.get_name()!r} canceled", task=scheduler_task)

            # except asyncio.TimeoutError:
            #     logger.warning(
            #         f"Task {aio_task.get_name()!r} not canceled, but timeouted - deadlock?", task=scheduler_task
            #     )

        logger.debug("All tasks stopped")

    async def reset(self):
        logger.debug("Performing scheduler clean")
        await self._shutdown_tasks()
        self._tasks.clear()
        self.alias_generator.reset()
        logger.debug("Scheduler cleared")

    def next_closest_task(self, tags: set[str] | None = None) -> SchedulerTask | None:
        # Sort tasks based on the next scheduled run time (using next()), handling None cases
        tasks = sorted(self._tasks.values(), key=lambda t: (t.schedule.next() is None, t.schedule.next()))
        for task in tasks:
            if tags is not None:
                # Check if the task's tags match
                if task.tags.issubset(tags):
                    return task
            else:
                return task
        return None

    def previous_closest_task(self, tags: set[str] | None = None) -> SchedulerTask | None:
        # Sort tasks based on the previous run time (using prev()), handling None cases
        tasks = sorted(self._tasks.values(), key=lambda t: (t.schedule.prev() is None, t.schedule.prev()), reverse=True)
        for task in tasks:
            if tags is not None:
                # Check if the task's tags match
                if task.tags.issubset(tags):
                    return task
            else:
                return task
        return None

    def __str__(self) -> str:
        # Scheduler meta heading
        scheduler_headings = "Scheduler Jobs\n\n"

        # Determine the maximum length for the "Alias" field, with a minimum of 5 and a maximum of 20
        max_alias_length = min(max(5, max(len(task.alias) for task in self._tasks.values())), 20)

        # Determine the maximum length for the "Tags" field, with a minimum of the length of "Tags" (4) and a maximum of 20
        max_tags_length = max(4, min(20, max(len(",".join(task.tags)) for task in self._tasks.values())))

        # Define column alignments, widths, and names
        c_align = ("^", "<", ">", ">", ">")
        c_width = (10, max_alias_length, max_tags_length, 20, 30)  # Dynamically set alias and tags width
        c_name = ("Type", "Alias", "Tags", "Time Left", "Next Run (Exact Time)")

        # Create format string for each column
        form = [f"{{{idx}:{align}{width}}}" for idx, (align, width) in enumerate(zip(c_align, c_width))]
        fstring = " ".join(form) + "\n"

        # Header row
        job_table = fstring.format(*c_name)
        job_table += fstring.format(*("-" * width for width in c_width))

        # Job rows
        tasks = sorted(self._tasks.values(), key=lambda t: t.schedule)

        for task in tasks:
            # Determine task type (once/periodic)
            task_type = "Periodic" if isinstance(task.schedule, SchedulePeriodic) else "Once"

            # Alias of the task, using str_cutoff to limit its length
            alias = str_cutoff(task.alias, max_alias_length)

            # Join tags with commas and use str_cutoff to limit the size to dynamic max_tags_length
            tags_str = str_cutoff(",".join(task.tags), max_tags_length) if task.tags else ""

            # Calculate time until next execution
            next_run = task.schedule.next()
            if next_run is not None:
                time_left = next_run - datetime.now(self.tz)
                time_left_str = str(time_left).split(".")[0]  # remove microseconds for better readability
                next_run_str = next_run.strftime("%Y-%m-%d %H:%M:%S %Z")
            else:
                time_left_str = "N/A"
                next_run_str = "N/A"

            # Add the task details to the table
            job_table += fstring.format(task_type, alias, tags_str, time_left_str, next_run_str)

        return scheduler_headings + job_table


# if __name__ == "__main__":

#     import sys

#     import uvloop
#     from logging_conf import configure_logging

#     configure_logging(log_level="debug")

#     import signal

#     STOP_SIGNALS = (signal.SIGHUP, signal.SIGINT, signal.SIGTERM)

#     async def main(loop):
#         stop_event = asyncio.Event()

#         # App termination handler
#         def stop_all() -> None:
#             stop_event.set()
#             logger.warning("Shutting down service! Press ^C again to terminate")

#             def terminate():
#                 sys.exit("\nTerminated!\n")

#             for sig in STOP_SIGNALS:
#                 loop.remove_signal_handler(sig)
#                 loop.add_signal_handler(sig, terminate)

#         for sig in STOP_SIGNALS:
#             loop.add_signal_handler(sig, stop_all)

#         s = Scheduler()

#         # async def printo():
#         #     print(s.tasks)

#         async def foo():
#             print("FOO!")

#         async def bar():

#             # print(s.next_closest_task())
#             # print(list(s._tasks.values()))
#             # print(s.previous_closest_task())
#             print(s)
#             print("BAR!")

#         async def tsk():
#             await asyncio.sleep(7)
#             print("ADDING TASK!")
#             s.periodic(bar, timedelta(seconds=2))

#         asyncio.create_task(tsk())

#         # s.once(s.reset, (datetime.now() + timedelta(seconds=5)).time())
#         s.periodic(foo, timedelta(seconds=1), tags={"hello"})
#         s.periodic(foo, timedelta(seconds=1), alias="HEHEHE")
#         s.periodic(bar, timedelta(seconds=2))
#         # s.periodic(s.reset, timedelta(seconds=3))
#         # await s.periodic(bar, timedelta(seconds=4))

#         await s.run(stop_event, exit_on_empty_schedule=True)

#     if sys.version_info >= (3, 11):
#         with asyncio.Runner(loop_factory=uvloop.new_event_loop) as runner:
#             runner.run(main(runner.get_loop()))
#     else:
#         event_loop = uvloop.new_event_loop()
#         event_loop.run_until_complete(main(event_loop))

#     # t2 = SchedulePeriodic(timedelta(seconds=5))
#     # t3 = SchedulePeriodic(timedelta(seconds=2))
#     # t4 = ScheduleOnce((datetime.now() + timedelta(seconds=6)).time())

#     # print([f"{x} - {str(x.next())}" for x in sorted([t1, t3, t2, t4])])
#     # import time

#     # time.sleep(4)
#     # print([f"{x} - {str(x.next())}" for x in sorted([t1, t3, t2, t4])])
