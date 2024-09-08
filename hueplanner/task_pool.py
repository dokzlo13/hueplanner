import asyncio

import structlog

logger = structlog.getLogger(__name__)


class AsyncTaskPool:
    def __init__(self):
        self.task_pool = set()

    def add(self, coro):
        """Starts an asyncio task and adds it to the task pool."""
        task = asyncio.create_task(coro)
        self.task_pool.add(task)
        # Remove task from pool when it is done
        task.add_done_callback(self.task_pool.discard)

    def count(self):
        """Returns the count of active tasks in the pool."""
        return len(self.task_pool)

    async def shutdown(self):
        """Cancels all active tasks and waits for their termination."""
        tasks = self.task_pool.copy()  # Copy to avoid modifying the set while iterating
        for task in tasks:
            if not task.done():
                task.cancel()  # Cancel running tasks
            try:
                await task  # Await task to ensure cancellation is complete
            except asyncio.CancelledError:
                logger.warning(f"Task {task.get_name()!r} terminated")
