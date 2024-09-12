import asyncio
import random
from abc import abstractmethod
from datetime import datetime, tzinfo
from typing import Awaitable, Callable, Protocol, runtime_checkable

import structlog

logger = structlog.getLogger(__name__)


@runtime_checkable
class Wrapper(Protocol):
    @abstractmethod
    async def execute(self, *args, **kwargs):
        pass

    def __call__(self, *args, **kwargs) -> Awaitable[None]:
        return self.execute(*args, **kwargs)

    def get_task_name(self):
        # Recursively get the name or repr of the task being executed
        func = getattr(self, "func", None)
        if isinstance(func, Wrapper):
            return repr(func)
        elif hasattr(func, "__name__"):
            return f"<{func.__name__}>"  # Return the function name if available
        else:
            return repr(func)  # Fallback to repr for other callable objects

    def __repr__(self):
        # Return a simple class name representation if no specific function is wrapped
        return f"{self.__class__.__name__}({self.get_task_name()})"


class ReliableWrapper(Wrapper):
    def __init__(
        self,
        func: Callable[..., Awaitable[None]],
        max_retries: int = 3,
        base_backoff: int = 1,
        silence_exceptions: tuple[type[Exception], ...] = (Exception,),
        always_raise_exceptions: tuple[type[Exception], ...] | None = None,
    ):
        self.func = func
        self.max_retries = max_retries
        self.base_backoff = base_backoff
        self.silence_exceptions = silence_exceptions
        self.always_raise_exceptions = always_raise_exceptions

    async def execute(self, *args, **kwargs):
        log = logger.bind(task=repr(self.func))
        attempt = 0
        while attempt < self.max_retries:
            try:
                # log.debug("Starting task with retries", attempt=attempt + 1, max_retries=self.max_retries)
                # Execute the function with provided args and kwargs
                result = await self.func(*args, **kwargs)
                # log.debug("Task completed successfully", attempt=attempt + 1)
                return result
            except self.silence_exceptions as e:
                if self.always_raise_exceptions and isinstance(e, self.always_raise_exceptions):
                    raise

                attempt += 1
                log.exception("Task raised an exception, retrying", attempt=attempt)
                backoff = self._get_backoff_time(attempt)
                if attempt >= self.max_retries:
                    log.error("Max retries reached, task failed", attempt=attempt)
                    break
                log.info("Retrying after backoff", attempt=attempt, backoff=round(backoff, 3))
                await asyncio.sleep(backoff)
        log.error("Task failed after all retries")
        return None

    def _get_backoff_time(self, attempt):
        backoff = self.base_backoff * (2 ** (attempt - 1))
        jitter = random.uniform(0, backoff * 0.1)
        return backoff + jitter


class TimeoutWrapper(Wrapper):
    def __init__(self, func: Callable[..., Awaitable[None]], run_until: datetime, tz: tzinfo | None = None):
        self.func = func
        self.run_until = run_until
        self.tz = tz

    async def execute(self, *args, **kwargs):
        log = logger.bind(task=repr(self.func))
        time_left = (self.run_until - datetime.now(self.tz)).total_seconds()
        if time_left <= 0:
            log.warning("Task cancelled due to run_until time exceeded")
            return None  # Task cancelled silently
        try:
            # log.debug("Starting task with timeout", timeout=time_left)
            return await asyncio.wait_for(self.func(*args, **kwargs), timeout=time_left)
        except asyncio.TimeoutError:
            log.warning("Task timed out and was cancelled")
            return None  # Silent cancellation


# class StopCancellationWrapper(Wrapper):
#     def __init__(self, func: Callable[..., Awaitable[None]], stop_event: asyncio.Event):
#         self.func = func
#         self.stop_event = stop_event

#     async def execute(self, *args, **kwargs):
#         stop_task = asyncio.create_task(self.stop_event.wait())
#         wrapped_task = asyncio.create_task(self.func(*args, **kwargs))  # type: ignore

#         done, pending = await asyncio.wait([stop_task, wrapped_task], return_when=asyncio.FIRST_COMPLETED)
#         for task in pending:
#             task.cancel()
#             try:
#                 await task  # Ensure is cancelled
#             except asyncio.CancelledError:
#                 if task is wrapped_task:
#                     logger.warning("Task cancelled due to stop_event trigger")

#         if not wrapped_task.cancelled():
#             # get the exception raised by a task
#             if exception := wrapped_task.exception():
#                 try:
#                     raise exception
#                 except Exception:
#                     logger.exception("Exception in the asyncio task", task=self)
#                     raise
