import asyncio
from contextlib import suppress
from dataclasses import dataclass
from typing import Awaitable, Callable

import structlog

from hueplanner.hue.v2.event_stream import HueEventStream
from hueplanner.hue.v2 import HueBridgeV2
from hueplanner.hue.v2.models import HueEvent, HueEventData
from hueplanner.task_pool import AsyncTaskPool

logger = structlog.getLogger(__name__)


@dataclass(slots=True)
class EventHandler:
    check: Callable[[HueEvent], Awaitable[bool]]
    handle: Callable[[HueEvent], Awaitable[None]]


class HueEventStreamListener:
    def __init__(self, bridge_v2: HueBridgeV2, task_pool: AsyncTaskPool) -> None:
        self.bridge_v2 = bridge_v2
        self.task_pool = task_pool
        self._handlers: list[EventHandler] = []

    async def _handle_event(self, event: HueEvent):
        for handler in self._handlers:
            if await handler.check(event):
                logger.info("Triggered event", hue_event=event, handler=handler.handle)
                await handler.handle(event)

    def clean_callbacks(self):
        self._handlers = []

    def register_callback(
        self,
        check: Callable[[HueEvent], Awaitable[bool]],
        handle: Callable[[HueEvent], Awaitable[None]],
    ):
        self._handlers.append(EventHandler(check, handle))

    async def run(self, stop_event: asyncio.Event):
        logger.debug("Reliable HUE event stream listener started")
        while not stop_event.is_set():
            event_stream = self.bridge_v2.event_stream()

            async def terminate():
                await stop_event.wait()
                logger.info("Terminating event listener")
                await event_stream.close()

            terminate_task = asyncio.create_task(terminate())

            try:
                async with event_stream as events:
                    logger.info("HUE event stream connected")
                    # Reset the retry counter on successful connection
                    retry_counter = 0
                    async for event in events:
                        # self.task_pool.add(self._handle_event(event))
                        await self._handle_event(event)
            except Exception:
                logger.exception("Event stream closed with error")
                terminate_task.cancel()
                with suppress(asyncio.CancelledError):
                    await terminate_task

                # Calculate backoff time
                backoff_time = min(2**retry_counter, 120)  # Exponential backoff with a cap
                logger.info(f"Reconnecting to event stream in {backoff_time} seconds.")
                await asyncio.sleep(backoff_time)
                retry_counter += 1  # Increment the retry counter after failure
                continue

            await terminate_task
        logger.info("Exited event listener reliable loop")
