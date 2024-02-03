import asyncio
from contextlib import suppress
from dataclasses import dataclass
from datetime import datetime, time, timedelta
from typing import Protocol

import structlog

from ..hue.v2.models import HueEvent
from .actions import EvaluatedAction
from .context import Context

logger = structlog.getLogger(__name__)

# - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -


class PlanTrigger(Protocol):
    async def apply_trigger(self, context: Context, action: EvaluatedAction):
        pass


# - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -


@dataclass
class PlanTriggerOnce(PlanTrigger):
    act_on: str
    alias: str | None = None
    scheduler_tag: str | None = None

    async def apply_trigger(self, context: Context, action: EvaluatedAction):
        logger.debug("Applying once trigger", act_on=str(self.act_on))
        alias = self.alias if self.alias is not None else self.act_on
        act_on_time = (await context.time_parser.parse(self.act_on)).timetz()
        await context.scheduler.once(
            action,
            act_on_time,
            alias=alias,
            tags={self.scheduler_tag} if self.scheduler_tag is not None else None,
        )


@dataclass
class PlanTriggerPeriodic(PlanTrigger):
    interval: timedelta
    first_run_time: time | None = None
    alias: str | None = None

    async def apply_trigger(self, context: Context, action: EvaluatedAction):
        logger.debug("Applying periodic trigger", interval=str(self.interval), first_run_time=str(self.first_run_time))
        await context.scheduler.cyclic(
            action, interval=self.interval, first_run_time=self.first_run_time, alias=self.alias
        )


@dataclass
class PlanTriggerImmediately(PlanTrigger):
    async def apply_trigger(self, context: Context, action: EvaluatedAction):
        logger.info(f"Executing action immediately: {action}")
        await action()


@dataclass
class PlanTriggerOnHueEvent(PlanTrigger, Protocol):
    _action: EvaluatedAction = None  # type: ignore

    async def apply_trigger(self, context: Context, action: EvaluatedAction):
        listen_task = asyncio.create_task(self._listener(context))
        self._action = action
        context.add_task_to_pool(listen_task)

    async def _handle_event(self, hevent: HueEvent):
        ...

    async def _listener(self, context: Context):
        retry_counter = 0  # Initialize the retry counter
        stop_event = context.stop_event
        bridge = context.hue_client_v2

        while not stop_event.is_set():
            event_stream = bridge.event_stream()

            async def terminate():
                await stop_event.wait()
                logger.info("Terminating event listener")
                await event_stream.close()

            terminate_task = asyncio.create_task(terminate())

            try:
                async with event_stream as events:
                    # Reset the retry counter on successful connection
                    retry_counter = 0
                    async for event in events:
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


@dataclass
class PlanTriggerOnHueButtonEvent(PlanTriggerOnHueEvent):
    resource_id: str = ""
    action: str = ""

    def __post_init__(self):
        if self.resource_id == "" or self.action == "":
            raise ValueError("Fields 'resource_id' and 'action' cannot be empty")

    async def _handle_event(self, hevent: HueEvent):
        for event in hevent.data:
            for data in event["data"]:
                if data["id"] == self.resource_id and data["type"] == "button":
                    report = data[data["type"]]["button_report"]
                    if report["event"] == self.action:
                        logger.info("Triggered event", hue_event=event)
                        return await self._action()
