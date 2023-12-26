import asyncio
import datetime
import heapq
from contextlib import suppress
from typing import Any, Callable

import structlog

logger = structlog.getLogger(__name__)


def str_cutoff(text: str, max_width: int | None = None) -> str:
    """Cuts off the string to fit the max_width with '...' appended if truncated."""
    if max_width is None:
        return text
    return text if len(text) <= max_width else text[: max_width - 3] + "..."


class Job:
    def __init__(
        self,
        next_run: datetime.datetime,
        coro: Callable,
        interval: datetime.timedelta | None,
        max_runs: int | None,
        retries: int,
        alias: str,
        args: tuple[Any, ...],
        kwargs: dict[str, Any],
        tags: set[str],
        tz: datetime.tzinfo | None,
    ):
        self.next_run = next_run
        self.coro = coro
        self.interval = interval
        self.max_runs = max_runs
        self.retries = retries
        self.alias = alias
        self.tags = tags
        self.tz = tz

        self.args = args
        self.kwargs = kwargs

        self.current_retry = 0
        self.run_count = 0
        self.success_count = 0
        self.fail_count = 0

    def match_tags(self, tags: set[str]) -> bool:
        return tags.issubset(self.tags)

    def must_run(self):
        if self.max_runs is not None:
            return self.run_count < self.max_runs
        return True

    async def execute(self, off_schedule: bool = False):
        assumed_execution_time = 6  # Assumed execution time for a job
        while self.must_run():
            try:
                await self.coro(*self.args, **self.kwargs)
                if off_schedule:
                    return
                self.success_count += 1
                self.fail_count = 0  # Reset fail counter on success
                self.current_retry = 0  # Reset retry counter on success
                logger.info("Job executed successfully.", alias=self.alias)
                break  # Exit the loop as job succeeded
            except Exception:
                logger.exception("Job failed with exception", alias=self.alias)
                if off_schedule:
                    logger.info("Job executed out of schedule, so no retries will be applied")
                    return
                self.fail_count += 1
                self.current_retry += 1

                # Check if we've exceeded retries
                if self.current_retry >= self.retries:
                    logger.error(f"Job failed after max retries ({self.retries})", alias=self.alias)
                    break

                # Calculate remaining time until next run
                now = datetime.datetime.now(self.tz)
                remaining_time = (self.next_run - now).total_seconds() if self.next_run else float("inf")

                # Calculate backoff time
                backoff = min(2**self.current_retry, 60)

                # Check if there's not enough time left for the next retry
                if (backoff + assumed_execution_time) > remaining_time:
                    logger.warning(
                        f"Job will not be retried due to time constraints. Remaining time {remaining_time:.2f}s. "
                        f"is less than required {backoff + assumed_execution_time}s.",
                        alias=self.alias,
                    )
                    break

                # Log and wait for the backoff period
                logger.warning(f"Job will be retried in {backoff}sec.", alias=self.alias)
                await asyncio.sleep(backoff)
                logger.warning(f"Retrying job {self.current_retry}/{self.retries}...", alias=self.alias)

            finally:
                self.run_count += 1

    def __lt__(self, other):
        return self.next_run < other.next_run

    def __repr__(self) -> str:
        fields = self._str()
        return (
            f"<Job type:{fields[0]} name:{fields[1]!r} due_at:{fields[2]!r} tz:{fields[3]!r} "
            f"due_in:{fields[4]!r} attempts:{fields[5]!r}>"
        )

    def _str(self, c_width: tuple[int, ...] | None = None) -> list[str]:
        """Return a list of string representations of the job's attributes, capped to column widths."""
        _width: tuple[int, ...]
        if c_width is None:
            _width = (None,) * 6  # type: ignore
        else:
            _width = c_width

        now = datetime.datetime.now(self.tz)
        job_type = str_cutoff("Once" if self.interval is None else "Cyclic", _width[0])
        function_name = str_cutoff(self.alias, _width[1])
        due_at = str_cutoff(self.next_run.strftime("%Y-%m-%d %H:%M:%S"), _width[2])
        tzinfo = str_cutoff(str(self.next_run.tzinfo) if self.next_run.tzinfo else "Local", _width[3])
        due_in_dt = self.next_run - now
        if due_in_dt < datetime.timedelta(0):
            due_in = str_cutoff("Expired: -" + str(now - self.next_run), _width[4])
        else:
            due_in = str_cutoff(str(due_in_dt), _width[4])
        attempts = str_cutoff(
            f"{self.success_count}/{self.max_runs if self.max_runs is not None else 'inf'}", _width[5]
        )  # Modify as per your job retry logic if any

        return [job_type, function_name, due_at, tzinfo, due_in, attempts]


class Scheduler:
    def __init__(self, tz: datetime.tzinfo | None = None, worker_count: int = 5):
        self.tz = tz
        self.jobs: list[Job] = []
        self.job_lookup: dict[str, Job] = {}  # Track jobs by their name
        self.alias_counts: dict[str, int] = {}  # Track counts for alias naming
        self.queue: asyncio.Queue[Job] = asyncio.Queue()  # Create a queue for jobs
        self.lock = asyncio.Lock()  # Create a lock for heap operations
        self.worker_count = worker_count

    async def _run_job(self, job: Job):
        # Execute the job and reschedule it if necessary
        if job.interval and job.must_run():
            job.next_run = datetime.datetime.now(tz=self.tz) + job.interval
            async with self.lock:  # Acquire lock before modifying the heap
                heapq.heappush(self.jobs, job)
        else:
            logger.debug("Executing last run for job", alias=job.alias)

        await job.execute()

    async def _worker(self, stop_event: asyncio.Event, worker_ready: asyncio.Event, name: str):
        logger.debug("Worker created", id=name)
        worker_ready.set()
        while not stop_event.is_set():
            job = await self.queue.get()  # Wait for a job from the queue
            logger.debug("Executing job in worker", id=name, alias=job.alias)
            await self._run_job(job)  # Run the job
            self.queue.task_done()  # Indicate the job is done

    def __str__(self) -> str:
        # Scheduler meta heading
        scheduler_headings = "Scheduler Jobs\n\n"
        # Define column alignments, widths, and names
        c_align = ("<", "<", "<", "<", ">", ">")
        c_width = (8, 20, 19, 16, 25, 10)
        c_name = ("Type", "Function/Alias", "Due At", "TZ Info", "Due In", "Attempts")

        # Create format string for each column
        form = [f"{{{idx}:{align}{width}}}" for idx, (align, width) in enumerate(zip(c_align, c_width))]
        fstring = " ".join(form) + "\n"

        # Header row
        job_table = fstring.format(*c_name)
        job_table += fstring.format(*("-" * width for width in c_width))

        # Job rows
        for job in sorted(self.jobs):
            job_details = job._str(c_width)  # Pass column widths to job string representation
            job_table += fstring.format(*job_details)

        return scheduler_headings + job_table

    def _calculate_next_occurrence(
        self, target_time: datetime.time | None, interval: datetime.timedelta | None = None
    ) -> datetime.datetime:
        now = datetime.datetime.now(tz=self.tz)
        if target_time is None:
            next_run = now.replace(second=0, microsecond=0)
            if interval is not None:
                next_run += interval
            return next_run
        today_target = datetime.datetime.combine(now.date(), target_time)
        if today_target > now:
            return today_target
        return today_target + (interval or datetime.timedelta(days=1))

    async def _schedule(
        self,
        coro: Callable,
        time: datetime.time | None = None,
        interval: datetime.timedelta | None = None,
        max_runs: int | None = None,
        retries: int = 0,
        alias: str | None = None,
        args: tuple[Any] | None = None,
        kwargs: dict[str, Any] | None = None,
        tags: set[str] | None = None,
    ):
        alias = alias or coro.__name__
        original_alias = alias
        if alias in self.job_lookup:
            # If alias already exists, append a counter to it
            counter = self.alias_counts.get(original_alias, 0) + 1
            alias = f"{original_alias}_{counter}"
            self.alias_counts[original_alias] = counter

        # Determine the next_run time
        now = datetime.datetime.now(tz=self.tz)
        if time is None:
            next_run = now + datetime.timedelta(seconds=1)  # Run as soon as possible
        else:
            scheduled_time = datetime.datetime.combine(now.date(), time, tzinfo=self.tz)
            if scheduled_time < now:
                # If the scheduled time for today has passed, schedule for the next day
                scheduled_time += datetime.timedelta(days=1)
                logger.info(
                    f"Time {time} has already passed. Scheduling {alias!r} for the next day at {scheduled_time}."
                )
            next_run = scheduled_time
        logger.debug(
            "Scheduling task",
            coro=coro,
            alias=alias,
            next_run=str(next_run),
            interval=interval,
            max_runs=max_runs,
            retries=retries,
            args=args,
            kwargs=kwargs,
            tags=tags,
            tz=self.tz,
        )

        job = Job(
            next_run,
            coro,
            interval,
            max_runs,
            retries,
            alias,
            args if args is not None else tuple(),
            kwargs if kwargs is not None else {},
            tags=tags if tags is not None else set(),
            tz=self.tz,
        )
        async with self.lock:
            heapq.heappush(self.jobs, job)
        self.job_lookup[alias] = job  # Track the job by its new alias

    async def cyclic(
        self,
        coro: Callable,
        interval: datetime.timedelta,
        first_run_time: datetime.time | None = None,
        max_runs: int | None = None,
        retries: int = 0,
        alias: str | None = None,
        args: tuple[Any] | None = None,
        kwargs: dict[str, Any] | None = None,
        tags: set[str] | None = None,
    ):
        await self._schedule(
            coro,
            time=first_run_time,
            max_runs=max_runs,
            interval=interval,
            retries=retries,
            alias=alias,
            args=args,
            kwargs=kwargs,
            tags=tags,
        )

    async def once(
        self,
        coro: Callable,
        time: datetime.time | None = None,
        alias: str | None = None,
        args: tuple[Any] | None = None,
        kwargs: dict[str, Any] | None = None,
        tags: set[str] | None = None,
    ):
        await self._schedule(coro, time, max_runs=1, alias=alias, args=args, kwargs=kwargs, tags=tags)

    async def daily(
        self,
        coro: Callable,
        time: datetime.time | None = None,
        alias: str | None = None,
        args: tuple[Any] | None = None,
        kwargs: dict[str, Any] | None = None,
        tags: set[str] | None = None,
    ):
        await self._schedule(coro, time, datetime.timedelta(days=1), alias=alias, args=args, kwargs=kwargs, tags=tags)

    async def hourly(
        self,
        coro: Callable,
        time: datetime.time | None = None,
        alias: str | None = None,
        args: tuple[Any] | None = None,
        kwargs: dict[str, Any] | None = None,
        tags: set[str] | None = None,
    ):
        await self._schedule(coro, time, datetime.timedelta(hours=1), alias=alias, args=args, kwargs=kwargs, tags=tags)

    async def minutely(
        self,
        coro: Callable,
        time: datetime.time | None = None,
        alias: str | None = None,
        args: tuple[Any] | None = None,
        kwargs: dict[str, Any] | None = None,
        tags: set[str] | None = None,
    ):
        await self._schedule(
            coro, time, datetime.timedelta(minutes=1), alias=alias, args=args, kwargs=kwargs, tags=tags
        )

    async def remove_job(self, alias: str):
        # Find and remove the job from both the heap and the lookup dictionary
        if alias not in self.job_lookup:
            logger.warning(f"No job found with the alias '{alias}'.")
            return

        job_to_remove = self.job_lookup.pop(alias)

        # Remove the job from the heap
        try:
            self.jobs.remove(job_to_remove)
            async with self.lock:
                heapq.heapify(self.jobs)  # Reorder the heap after removing a job
            logger.info(f"Successfully removed job '{alias}'.")
        except ValueError:
            logger.warning(f"Job '{alias}' could not be found in the job list.")

    def total_jobs(self) -> int:
        return len(self.jobs)

    async def next_closest_job(self, time: datetime.time | None = None, tags: set[str] | None = None) -> Job | None:
        if time is None:
            now = datetime.datetime.now(tz=self.tz).time()  # Current time, ignore date
        else:
            now = time
        closest_next_job = None
        shortest_time_diff = datetime.timedelta.max  # Initialize with max timedelta

        async with self.lock:
            for job in self.jobs:
                if tags is not None and not job.match_tags(tags):
                    continue

                job_time = job.next_run.timetz()  # Get the time of the next run

                # Convert times to timedelta since midnight to calculate duration
                now_delta = datetime.timedelta(
                    hours=now.hour, minutes=now.minute, seconds=now.second, microseconds=now.microsecond
                )
                job_time_delta = datetime.timedelta(
                    hours=job_time.hour,
                    minutes=job_time.minute,
                    seconds=job_time.second,
                    microseconds=job_time.microsecond,
                )

                # Calculate time difference, considering next day rollover
                if job_time < now:
                    # if job time is earlier in the day, consider it as next day for the calculation
                    time_diff = datetime.timedelta(days=1) + job_time_delta - now_delta
                else:
                    time_diff = job_time_delta - now_delta

                # Update closest job if this job's time is closer and is in the future
                if datetime.timedelta() <= time_diff < shortest_time_diff:
                    shortest_time_diff = time_diff
                    closest_next_job = job

        return closest_next_job

    async def previous_closest_job(self, time: datetime.time | None = None, tags: set[str] | None = None) -> Job | None:
        if time is None:
            now = datetime.datetime.now(tz=self.tz).time()  # Current time, ignore date
        else:
            now = time
        closest_prev_job = None
        shortest_time_diff = datetime.timedelta.max  # Initialize with max timedelta

        async with self.lock:
            for job in self.jobs:
                if tags is not None and not job.match_tags(tags):
                    continue

                job_time = job.next_run.timetz()  # Get the time of the next run

                # Convert times to timedelta since midnight to calculate duration
                now_delta = datetime.timedelta(
                    hours=now.hour, minutes=now.minute, seconds=now.second, microseconds=now.microsecond
                )
                job_time_delta = datetime.timedelta(
                    hours=job_time.hour,
                    minutes=job_time.minute,
                    seconds=job_time.second,
                    microseconds=job_time.microsecond,
                )

                # Calculate time difference for past times
                if job_time > now:
                    # if job time is later in the day, consider it as the previous day for calculation
                    time_diff = now_delta + datetime.timedelta(days=1) - job_time_delta
                else:
                    time_diff = now_delta - job_time_delta

                # Update closest previous job if this job's time is closer and is in the past
                if datetime.timedelta() < time_diff < shortest_time_diff:
                    shortest_time_diff = time_diff
                    closest_prev_job = job

        return closest_prev_job

    async def _spawn_workers(self, stop_event: asyncio.Event) -> set[asyncio.Task]:
        workers = set()
        workers_ready = set()
        for i in range(self.worker_count):
            worker_ready = asyncio.Event()
            workers_ready.add(worker_ready)
            name = f"worker-{i}"
            workers.add(asyncio.create_task(self._worker(stop_event, worker_ready, name), name=name))
        await asyncio.gather(*[event.wait() for event in workers_ready])
        logger.debug("Workers pool created")
        return workers

    async def reset(self):
        async with self.lock:
            self.jobs.clear()
        self.job_lookup.clear()
        self.alias_counts.clear()
        logger.info("Scheduler has been reset")

    async def run(self, stop_event: asyncio.Event):
        workers = await self._spawn_workers(stop_event)
        while not stop_event.is_set():
            if not self.jobs:
                with suppress(asyncio.TimeoutError):
                    await asyncio.wait_for(stop_event.wait(), 1.0)
                continue
            next_job = self.jobs[0]
            if next_job.next_run <= datetime.datetime.now(tz=self.tz):
                async with self.lock:
                    job = heapq.heappop(self.jobs)
                await self.queue.put(job)  # Put the job into the queue instead of running directly
            else:
                with suppress(asyncio.TimeoutError):
                    await asyncio.wait_for(stop_event.wait(), 1.0)

        for worker in workers:
            if not worker.done():
                worker.cancel()
            with suppress(asyncio.CancelledError):
                await worker
        await self.queue.join()  # Wait for the queue to be fully processed
        logger.debug("Workers pool stopped")


# Example usage
async def main():
    scheduler = Scheduler()
    stop_event = asyncio.Event()

    async def my_task():
        print(scheduler)
        print("Task executed:", datetime.datetime.now())

    async def raiser():
        raise Exception("WTF!")

    # Schedule tasks
    # await scheduler.once(my_task)  # Run as soon as possible
    # t = (datetime.datetime.now() + datetime.timedelta(seconds=10)).timetz()
    # await scheduler.daily(my_task, t)  # Run daily at current time + 10 seconds
    # await scheduler.hourly(my_task)  # Run hourly, first task will be executed ASAP
    first_run_time = (datetime.datetime.now() + datetime.timedelta(seconds=3)).time()
    await scheduler.cyclic(my_task, datetime.timedelta(seconds=3), first_run_time=first_run_time, alias="qwe!")

    print(scheduler)
    scheduler_task = asyncio.create_task(scheduler.run(stop_event))
    await asyncio.sleep(10)
    stop_event.set()
    print(scheduler)
    await scheduler_task


if __name__ == "__main__":
    asyncio.run(main())
