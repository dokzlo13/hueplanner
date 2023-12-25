import asyncio
import signal
import sys
from contextlib import suppress

import pytz
import structlog

from hueplanner.geo import get_location
from hueplanner.hue import HueBridgeFactory
from hueplanner.logging_conf import configure_logging
from hueplanner.planner import (
    Context,
    PlanActionActivateSceneByName,
    PlanActionCallback,
    PlanActionToggleCurrentScene,
    PlanEntry,
    Planner,
    PlanTriggerImmediately,
    PlanTriggerOnce,
    PlanTriggerOnHueButtonEvent,
)
from hueplanner.scheduler import Scheduler
from hueplanner.time_parser import TimeParser

logger = structlog.getLogger(__name__)

STOP_SIGNALS = (signal.SIGHUP, signal.SIGINT, signal.SIGTERM)


async def main(loop):
    configure_logging("debug")

    # Global stop event to stop 'em all!
    stop_event = asyncio.Event()

    # App termination handler
    def stop_all() -> None:
        stop_event.set()
        logger.warning("Shutting down service! Press ^C again to terminate")

        def terminate():
            sys.exit("\nTerminated!\n")

        for sig in STOP_SIGNALS:
            loop.remove_signal_handler(sig)
            loop.add_signal_handler(sig, terminate)

    for sig in STOP_SIGNALS:
        loop.add_signal_handler(sig, stop_all)

    bridge_factory = HueBridgeFactory(address="192.168.10.12", access_token="JxDOFTiu4rtEUo3YuRS2GQ7bT7b67CvLFdx6V1lO")
    bridge_v2 = bridge_factory.api_v2()
    await bridge_v2.connect()

    bridge_v1 = bridge_factory.api_v1()
    await bridge_v1.connect()

    # Storing handlers for created asyncio tasks
    tasks = set()

    async def wait_tasks_shutdown():
        finished, pending = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)

        finished_task = finished.pop()
        logger.warning(f"Task {finished_task.get_name()!r} exited, shutting down gracefully")

        graceful_shutdown_max_time = 60  # seconds
        for task in pending:
            with suppress(asyncio.TimeoutError):
                logger.debug(f"Waiting task {task.get_name()!r} to shutdown gracefully")
                await asyncio.wait_for(task, graceful_shutdown_max_time / len(tasks))
                logger.debug(f"Task {task.get_name()!r} exited")

        # If tasks not exited gracefully, terminate them by cancelling
        for task in pending:
            if not task.done():
                task.cancel()

        for task in pending:
            try:
                await task
            except asyncio.CancelledError:
                logger.warning(f"Task {task.get_name()!r} terminated")

    location = get_location("Espoo", "Finland")
    tz = pytz.timezone(location.timezone)

    # Running scheduler
    scheduler = Scheduler(tz=tz)
    tasks.add(asyncio.create_task(scheduler.run(stop_event), name="scheduler_task"))

    context = Context(
        stop_event=stop_event,
        hue_client_v1=bridge_v1,
        hue_client_v2=bridge_v2,
        scheduler=scheduler,
        location=location,
    )

    async def run_previous_scheduled_job():
        job = await scheduler.previous_closest_job()
        if job is not None:
            logger.debug("Executing closest previous job to current time", job=job)
            await job.execute(off_schedule=True)

    async def evaluate_plan():
        tp = TimeParser.from_location(location)
        for k, v in tp.variables.items():
            logger.debug(f"Astronomical events for today: {k:<10}: {str(v)}")
        plan = [
            PlanEntry(
                trigger=PlanTriggerOnce(act_on=tp.parse("@dawn").timetz(), alias="@dawn"),
                action=PlanActionActivateSceneByName(name="Energize"),
            ),
            PlanEntry(
                trigger=PlanTriggerOnce(act_on=tp.parse("@noon").timetz(), alias="@noon"),
                action=PlanActionActivateSceneByName(name="Concentrate"),
            ),
            PlanEntry(
                trigger=PlanTriggerOnce(act_on=tp.parse("@sunset - 2H").timetz(), alias="@sunset - 2H"),
                action=PlanActionActivateSceneByName(name="Read"),
            ),
            PlanEntry(
                trigger=PlanTriggerOnce(act_on=tp.parse("@dusk").timetz(), alias="@dusk"),
                action=PlanActionActivateSceneByName(name="Relax"),
            ),
            PlanEntry(
                trigger=PlanTriggerOnce(act_on=tp.parse("@midnight - 30M").timetz(), alias="@midnight - 30M"),
                action=PlanActionActivateSceneByName(name="Rest"),
            ),
            # Button toggle lights
            PlanEntry(
                trigger=PlanTriggerOnHueButtonEvent(
                    action="initial_press", resource_id="1e53050b-ca07-44f3-977f-ab0477e5e911"
                ),
                action=PlanActionToggleCurrentScene(),
            ),
            # This task will set scene which is nearest to current schedule (previous)
            PlanEntry(
                trigger=PlanTriggerImmediately(),
                action=PlanActionCallback(run_previous_scheduled_job),
            ),
            # Re-evaluate plan on midnight
            PlanEntry(
                trigger=PlanTriggerOnce(act_on=tp.parse("@midnight + 1H").timetz(), alias="Evaluate plan"),
                action=PlanActionCallback(evaluate_plan),
            ),
        ]
        await context.reset()
        await Planner(context).apply_plan(plan)

    await evaluate_plan()

    async def periodic_print_schedule(stop_event, sleep):
        while not stop_event.is_set():
            logger.debug("Current schedule:")
            print(scheduler)
            with suppress(asyncio.TimeoutError):
                await asyncio.wait_for(stop_event.wait(), sleep)

    tasks.add(asyncio.create_task(periodic_print_schedule(stop_event, 60), name="schedule_periodic_print"))
    tasks.add(asyncio.create_task(stop_event.wait(), name="stop_event_wait"))
    logger.info("Tasks started, waiting for termination signal.")
    await wait_tasks_shutdown()
    await context.shutdown()
    await bridge_v2.close()
    await bridge_v1.close()


if __name__ == "__main__":
    loop = asyncio.new_event_loop()
    loop.run_until_complete(main(loop))
