import argparse
import asyncio
import os
import signal
import sys
from contextlib import suppress

import structlog
import uvloop
from zoneinfo import ZoneInfo

from hueplanner.dsl import load_plan
from hueplanner.geo import astronomical_variables_from_location, get_location
from hueplanner.hue import HueBridgeFactory
from hueplanner.logging_conf import configure_logging
from hueplanner.planner import (
    Context,
    PlanActionCallback,
    PlanEntry,
    Planner,
    PlanTriggerOnce,
)
from hueplanner.scheduler import Scheduler
from hueplanner.settings import load_settings
from hueplanner.storage.memory import InMemoryKeyValueStorage
from hueplanner.storage.sqlite import SqliteKeyValueStorage
from hueplanner.time_parser import TimeParser

logger = structlog.getLogger(__name__)

STOP_SIGNALS = (signal.SIGHUP, signal.SIGINT, signal.SIGTERM)


async def graceful_shutdown(loop, signal=None):
    """Cancel all tasks and gracefully shut down the asyncio loop."""
    tasks = [t for t in asyncio.all_tasks(loop) if t is not asyncio.current_task()]
    for task in tasks:
        task.cancel()
    await asyncio.gather(*tasks, return_exceptions=True)
    loop.stop()


def _environ_or_required(key):
    return {"default": os.environ.get(key)} if os.environ.get(key) else {"required": True}


async def main(loop):
    parser = argparse.ArgumentParser()
    parser.add_argument("-c", "--config", **_environ_or_required("CONFIG_FILE"))  # type: ignore
    args = parser.parse_args()
    # restore = args.restore
    config_file = args.config

    settings = load_settings(config_file)
    configure_logging(settings.log.level, console_colors=settings.log.colors)

    plan = load_plan(config_file)

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

    bridge_factory = HueBridgeFactory(address=settings.hue_bridge.addr, access_token=settings.hue_bridge.username)
    bridge_v1 = bridge_factory.api_v1()
    bridge_v2 = bridge_factory.api_v2()

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

    if settings.database.path:
        logger.warning("Using sqlite engine to store data", db_path=settings.database.path)
        storage_cls = SqliteKeyValueStorage
        db_path = settings.database.path
    else:
        logger.warning("Using in-memory engine to store data")
        storage_cls = InMemoryKeyValueStorage
        db_path = ""

    async with storage_cls(db_path) as storage, bridge_v1, bridge_v2:
        geocache = await storage.create_collection("geocache")
        time_variables = await storage.create_collection("time_variables")
        scenes_collection = await storage.create_collection("scenes")
        await scenes_collection.delete_all()
        logger.debug("scenes_collection cache flushed")

        location = None
        if settings.geo.location_name:
            location = await geocache.get("location_info")
            if location is None:
                logger.warning("No geo location data storing, obtaining geocoded location...")
                location = get_location(settings.geo.location_name)
                logger.info("Geocoded location obtained form geocoder", location=location)
                await geocache.set("location_info", location)
            else:
                logger.info("Geocoded location available from cache", location=location)
        else:
            logger.warning("No geo_location_info provided, time variables will be unavailable.")
            if (await time_variables.size()) > 0:
                await time_variables.delete_all()
                logger.warning("time_variables cache flushed")

        # Setting timezone
        tz = None
        if location is not None:
            loc_tz = ZoneInfo(location.timezone)
            if settings.tz:
                logger.warning(
                    "Settings provides different timezone, then location. Settings value will be used.",
                    location=loc_tz,
                    settings=settings.tz,
                )
                tz = settings.tz
            else:
                tz = loc_tz
                logger.warning("Using timezone from location", tz=tz)

        if tz is None and settings.tz:
            tz = settings.tz
            logger.warning("Using timezone from 'tz' setting", tz=tz)

        if tz is None:
            from tzlocal import get_localzone

            tz = get_localzone()
            logger.warning("Timezone not provided, using local timezone", tz=tz)

        # Running scheduler
        scheduler = Scheduler(tz=tz)
        tasks.add(asyncio.create_task(scheduler.run(stop_event), name="scheduler_task"))

        # Creating context
        context = Context(
            stop_event=stop_event,
            hue_client_v1=bridge_v1,
            hue_client_v2=bridge_v2,
            scheduler=scheduler,
            scenes=scenes_collection,
            time_parser=TimeParser(tz, time_variables),
        )

        async def evaluate_plan(plan):
            if location is not None:
                for k, v in astronomical_variables_from_location(location).items():
                    logger.info(f"Astronomical event for today: {k:<10}: {str(v)}")
                    await time_variables.set(k, v)

            await context.reset()
            await Planner(context).apply_plan(plan)
            logger.info("Plan evaluated. Schedule:")
            print(scheduler, flush=True)

        if settings.continuity.re_evaluate_plan:
            logger.warning(
                "Applying continuity modifier to the plan", re_evaluate_plan=settings.continuity.re_evaluate_plan
            )
            plan.append(
                PlanEntry(
                    trigger=PlanTriggerOnce(act_on=settings.continuity.re_evaluate_plan, alias="Evaluate plan"),
                    action=PlanActionCallback(evaluate_plan, plan),
                ),
            )
        await evaluate_plan(plan)

        if settings.log.print_schedule_interval > 0:
            logger.info("Starting periodic schedule printing", interval=f"{settings.log.print_schedule_interval}s")

            async def periodic_print_schedule(stop_event, sleep):
                while not stop_event.is_set():
                    with suppress(asyncio.TimeoutError):
                        await asyncio.wait_for(stop_event.wait(), sleep)

                    logger.debug("Current schedule:")
                    print(scheduler, flush=True)

            tasks.add(
                asyncio.create_task(
                    periodic_print_schedule(stop_event, settings.log.print_schedule_interval),
                    name="schedule_periodic_print",
                )
            )

        tasks.add(asyncio.create_task(stop_event.wait(), name="stop_event_wait"))
        logger.info("Tasks started, waiting for termination signal.")
        await wait_tasks_shutdown()
        await context.shutdown()


if __name__ == "__main__":
    if sys.version_info >= (3, 11):
        with asyncio.Runner(loop_factory=uvloop.new_event_loop) as runner:
            runner.run(main(runner.get_loop()))
    else:
        event_loop = uvloop.new_event_loop()
        event_loop.run_until_complete(main(event_loop))
