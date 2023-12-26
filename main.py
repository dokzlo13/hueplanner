import asyncio
import signal
import sys
from contextlib import suppress
from zoneinfo import ZoneInfo

import structlog
import uvloop

from hueplanner import settings
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
    configure_logging(settings.LOG_LEVEL, console_colors=settings.LOG_COLORS)

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

    bridge_factory = HueBridgeFactory(address=settings.HUE_BRIDGE_ADDR, access_token=settings.HUE_BRIDGE_USERNAME)
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

    location = get_location(settings.GEO_LOCATION_NAME)
    tz = ZoneInfo(location.timezone)
    # Running scheduler
    scheduler = Scheduler(tz=tz)
    logger.info("Using timezone", tz=repr(scheduler.tz))
    tasks.add(asyncio.create_task(scheduler.run(stop_event), name="scheduler_task"))

    context = Context(
        stop_event=stop_event,
        hue_client_v1=bridge_v1,
        hue_client_v2=bridge_v2,
        scheduler=scheduler,
        location=location,
    )

    async def run_previous_scheduled_job():
        job = await scheduler.previous_closest_job(tags={"scene"})
        if job is None:
            logger.warning("No previous closest job available by time")
            job = await scheduler.next_closest_job(tags={"scene"})
        if job is None:
            logger.warning("No next closest job available by time")
            return
        logger.debug("Executing closest scene job to current time", job=job)
        await job.execute(off_schedule=True)

    # TODO: Plan parser
    async def evaluate_plan():
        tp = TimeParser.from_location(location)
        for k, v in tp.variables.items():
            logger.info(f"Astronomical events for today: {k:<10}: {str(v)}")
        plan = [
            PlanEntry(
                trigger=PlanTriggerOnce(act_on=tp.parse("@dawn").timetz(), alias="@dawn", scheduler_tag="scene"),
                action=PlanActionActivateSceneByName(name="Energize"),
            ),
            PlanEntry(
                trigger=PlanTriggerOnce(act_on=tp.parse("@noon").timetz(), alias="@noon", scheduler_tag="scene"),
                action=PlanActionActivateSceneByName(name="Concentrate"),
            ),
            PlanEntry(
                trigger=PlanTriggerOnce(act_on=tp.parse("@sunset - 2H").timetz(), alias="@sunset - 2H", scheduler_tag="scene"),
                action=PlanActionActivateSceneByName(name="Read"),
            ),
            PlanEntry(
                trigger=PlanTriggerOnce(act_on=tp.parse("@dusk").timetz(), alias="@dusk", scheduler_tag="scene"),
                action=PlanActionActivateSceneByName(name="Relax"),
            ),
            PlanEntry(
                trigger=PlanTriggerOnce(
                    act_on=tp.parse("@midnight - 30M").timetz(), alias="@midnight - 30M", scheduler_tag="scene"
                ),
                action=PlanActionActivateSceneByName(name="Rest"),
            ),
            # Button toggle lights
            PlanEntry(
                trigger=PlanTriggerOnHueButtonEvent(
                    action="initial_press", resource_id="1e53050b-ca07-44f3-977f-ab0477e5e911"
                ),
                action=PlanActionToggleCurrentScene(fallback_run_job_tag="scene"),
            ),
            # Re-evaluate plan on midnight
            PlanEntry(
                trigger=PlanTriggerOnce(act_on=tp.parse("@midnight + 1H").timetz(), alias="Evaluate plan"),
                action=PlanActionCallback(evaluate_plan),
            ),
        ]
        await context.reset()
        await Planner(context).apply_plan(plan)
        logger.info("New schedule")
        print(scheduler)

    await evaluate_plan()

    if settings.PRINT_SCHEDULE_INTERVAL > 0:
        logger.info("Starting periodic schedule printing")

        async def periodic_print_schedule(stop_event, sleep):
            while not stop_event.is_set():
                logger.debug("Current schedule:")
                print(scheduler, flush=True)
                with suppress(asyncio.TimeoutError):
                    await asyncio.wait_for(stop_event.wait(), sleep)

        tasks.add(
            asyncio.create_task(
                periodic_print_schedule(stop_event, settings.PRINT_SCHEDULE_INTERVAL),
                name="schedule_periodic_print",
            )
        )

    tasks.add(asyncio.create_task(stop_event.wait(), name="stop_event_wait"))
    logger.info("Tasks started, waiting for termination signal.")
    await wait_tasks_shutdown()
    await context.shutdown()
    await bridge_v2.close()
    await bridge_v1.close()


if __name__ == "__main__":
    if sys.version_info >= (3, 11):
        with asyncio.Runner(loop_factory=uvloop.new_event_loop) as runner:
            runner.run(main(runner.get_loop()))
    else:
        event_loop = uvloop.new_event_loop()
        event_loop.run_until_complete(main(event_loop))
