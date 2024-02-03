import asyncio
import signal
import sys
from contextlib import suppress

import structlog
import uvloop
from zoneinfo import ZoneInfo

from hueplanner import settings
from hueplanner.geo import astronomical_variables_from_location, get_location
from hueplanner.hue import HueBridgeFactory
from hueplanner.logging_conf import configure_logging
from hueplanner.planner import (
    Context,
    PlanActionCallback,
    PlanActionSequence,
    PlanActionStoreSceneByName,
    PlanActionToggleStoredScene,
    PlanEntry,
    Planner,
    PlanTriggerImmediately,
    PlanTriggerOnce,
    PlanTriggerOnHueButtonEvent,
)
from hueplanner.scheduler import Scheduler
from hueplanner.storage.sqlite import SqliteKeyValueStorage
from hueplanner.storage.memory import InMemoryKeyValueStorage
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
                
    if settings.DATABASE_PATH:
        logger.warning("Using sqlite engine to store data", db_path=settings.DATABASE_PATH)
        storage_cls = SqliteKeyValueStorage
    else:
        logger.warning("Using in-memory engine to store data")
        storage_cls = InMemoryKeyValueStorage

    async with storage_cls(settings.DATABASE_PATH) as storage, bridge_v1, bridge_v2:
        geocache = await storage.create_collection("geocache")
        time_variables = await storage.create_collection("time_variables")
        scenes_collection = await storage.create_collection("scenes")
        await scenes_collection.delete_all()
        
        location = await geocache.get("location_info")
        if location is None:
            logger.warning("No geo location data storing, obtaining geocoded location...")
            location = get_location(settings.GEO_LOCATION_NAME)
            await geocache.set("location_info", location)
        else:
            logger.info("Geocoded location available from cache", location=location)

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
            scenes=scenes_collection,
            time_parser=TimeParser(time_variables),
        )

        # TODO: Plan parser
        def multi_group_same_scene(name: str, groups: list[int]):
            return PlanActionSequence(
                *[PlanActionStoreSceneByName(store_as=f"#scene:group-{gr}", name=name, group=gr) for gr in groups]
            )
        async def evaluate_plan():
            for k, v in astronomical_variables_from_location(location).items():
                logger.info(f"Astronomical events for today: {k:<10}: {str(v)}")
                await time_variables.set(k, v)

            plan = [
                PlanEntry(
                    trigger=PlanTriggerOnce(act_on="@dawn", scheduler_tag="scene"),
                    action=multi_group_same_scene("Energize", [2, 81]),
                ),
                PlanEntry(
                    trigger=PlanTriggerOnce(act_on="@noon", scheduler_tag="scene"),
                    action=multi_group_same_scene("Concentrate", [2, 81]),
                ),
                PlanEntry(
                    trigger=PlanTriggerOnce(act_on="@sunset - 1H", scheduler_tag="scene"),
                    action=multi_group_same_scene("Read", [2, 81]),
                ),
                PlanEntry(
                    trigger=PlanTriggerOnce(act_on="@dusk", scheduler_tag="scene"),
                    action=multi_group_same_scene("Relax", [2, 81]),
                ),
                PlanEntry(
                    trigger=PlanTriggerOnce(act_on="@midnight - 30M", alias="@midnight - 30M", scheduler_tag="scene"),
                    action=multi_group_same_scene("Rest", [2, 81]),
                ),
                # Button toggle lights
                PlanEntry(
                    trigger=PlanTriggerOnHueButtonEvent(
                        action="initial_press", resource_id="1e53050b-ca07-44f3-977f-ab0477e5e911"
                    ),
                    action=PlanActionToggleStoredScene(stored_scene="#scene:group-2", fallback_run_job_tag="scene"),
                ),
                PlanEntry(
                    trigger=PlanTriggerOnHueButtonEvent(
                        action="initial_press", resource_id="f0994222-7f20-42e4-95d1-a548a7930ff1"
                    ),
                    action=PlanActionToggleStoredScene(stored_scene="#scene:group-81", fallback_run_job_tag="scene"),
                ),
                # Re-evaluate plan on midnight
                PlanEntry(
                    trigger=PlanTriggerOnce(act_on="@midnight + 1H", alias="Evaluate plan"),
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
                    with suppress(asyncio.TimeoutError):
                        await asyncio.wait_for(stop_event.wait(), sleep)

                    logger.debug("Current schedule:")
                    print(scheduler, flush=True)

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
        await storage.close()


if __name__ == "__main__":
    if sys.version_info >= (3, 11):
        with asyncio.Runner(loop_factory=uvloop.new_event_loop) as runner:
            runner.run(main(runner.get_loop()))
    else:
        event_loop = uvloop.new_event_loop()
        event_loop.run_until_complete(main(event_loop))
