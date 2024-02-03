import asyncio
from datetime import datetime

import structlog

from ..hue import HueBridgeV1, HueBridgeV2
from ..hue.v1.models import Scene
from ..scheduler import Scheduler
from ..storage.interface import IKeyValueCollection
from ..time_parser import TimeParser

logger = structlog.getLogger(__name__)


class Context:
    def __init__(
        self,
        stop_event: asyncio.Event,
        scheduler: Scheduler,
        hue_client_v1: HueBridgeV1,
        hue_client_v2: HueBridgeV2,
        scenes: IKeyValueCollection,
        time_parser: TimeParser,
    ) -> None:
        self.stop_event = stop_event
        self.scheduler: Scheduler = scheduler
        self.hue_client_v1: HueBridgeV1 = hue_client_v1
        self.hue_client_v2: HueBridgeV2 = hue_client_v2
        self.scenes: IKeyValueCollection[str, Scene] = scenes
        self.time_parser = time_parser

        # TODO: better way to manage global context
        self.task_pool: set[asyncio.Task] = set()

    def finished(self) -> bool:
        if self.scheduler.total_jobs() == 0 and len(self.task_pool) == 0:
            return True
        return False

    async def shutdown(self):
        tasks = self.task_pool.copy()
        for task in tasks:
            if not task.done():
                task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                logger.warning(f"Task {task.get_name()!r} terminated")

    async def reset(self):
        await asyncio.gather(self.scheduler.reset(), self.shutdown())

    def add_task_to_pool(self, task: asyncio.Task):
        self.task_pool.add(task)
        task.add_done_callback(self.task_pool.discard)
