import argparse
import asyncio
import os
import signal
import sys
from contextlib import suppress
from datetime import tzinfo

import structlog
import uvloop
from pyaml_env import parse_config

from hueplanner.dsl import load_plan_from_obj
from hueplanner.event_listener import HueEventStreamListener
from hueplanner.healthcheck import HealthcheckServer
from hueplanner.hue import HueBridgeFactory
from hueplanner.ioc import IOC, Factory, Singleton, SingletonFactory
from hueplanner.logging_conf import configure_logging
from hueplanner.planner import Plan, Planner
from hueplanner.scheduler import Scheduler
from hueplanner.settings import Settings
from hueplanner.storage.interface import IKeyValueStorage
from hueplanner.storage.memory import InMemoryKeyValueStorage
from hueplanner.storage.sqlite import SqliteKeyValueStorage

logger = structlog.getLogger(__name__)

STOP_SIGNALS = (signal.SIGHUP, signal.SIGINT, signal.SIGTERM)


def _environ_or_required(key):
    return {"default": os.environ.get(key)} if os.environ.get(key) else {"required": True}


async def main(loop):
    parser = argparse.ArgumentParser()
    parser.add_argument("-c", "--config", **_environ_or_required("CONFIG_FILE"))  # type: ignore
    args = parser.parse_args()

    config = parse_config(args.config, tag=None, default_value=None)  # type: ignore
    settings = Settings.model_validate(config.get("settings", {}))

    configure_logging(settings.log.level, console_colors=settings.log.colors)

    plan = load_plan_from_obj(config.get("plan", {}))

    # Global stop event to stop 'em all!
    stop_event = asyncio.Event()
    # Event to signal when service is ready
    service_ready = asyncio.Event()
    service_ready.clear()

    async def healthcheck_live(context):
        return not stop_event.is_set()

    async def healthcheck_ready(context):
        return bool(service_ready.is_set())

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

    # Storing handlers for created asyncio tasks
    tasks = set()

    # HealthCheck must start ASAP, to make health probes accessible.
    if settings.healthcheck:
        health_check_server = HealthcheckServer(healthcheck_live, healthcheck_ready, context=None)
        tasks.add(
            asyncio.create_task(
                health_check_server.run(stop_event, settings.healthcheck.host, settings.healthcheck.port),
                name="health_check",
            )
        )
        logger.info("HealthCheck server task created", task_name="health_check")

    async def wait_tasks_shutdown():
        finished, pending = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
        service_ready.clear()

        finished_task = finished.pop()
        logger.warning(f"Task {finished_task.get_name()!r} exited, shutting down gracefully")

        graceful_shutdown_max_time = 5.0  # seconds
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

    bridge_factory = HueBridgeFactory(address=settings.hue_bridge.addr, access_token=settings.hue_bridge.username)
    bridge_v1 = bridge_factory.api_v1()
    bridge_v2 = bridge_factory.api_v2()

    async with storage_cls(db_path) as storage, bridge_v1, bridge_v2:
        tz = settings.tz
        if tz is None:
            from tzlocal import get_localzone

            tz = get_localzone()
            logger.warning("Timezone not provided, using local timezone", tz=str(tz))
        else:
            logger.warning("Using timezone", tz=str(tz))

        # Running scheduler
        scheduler = Scheduler(tz=tz)

        ioc = IOC()

        # Define timezone
        ioc.declare(tzinfo, tz)

        # Storing hue bridge API's
        ioc.auto_declare(bridge_v1)
        ioc.auto_declare(bridge_v2)

        # Storage reference
        ioc.declare(IKeyValueStorage, storage)

        # Scheduler
        ioc.auto_declare(scheduler)

        def event_listener():
            logger.debug("Creating HueEventStream...")
            listener = HueEventStreamListener(bridge_v2)
            tasks.add(asyncio.create_task(listener.run(stop_event), name="hue_stream_listener"))
            logger.info("HueEventStream created")
            return listener

        # If someone asks for event listener
        ioc.declare(HueEventStreamListener, SingletonFactory(Factory(event_listener)))

        # Global Stop Event
        ioc.auto_declare(stop_event)

        # keeping link for itself, because plan entries may want ioc itself as dependency
        ioc.auto_declare(ioc)

        ioc.declare(Plan, Singleton(plan))

        # Applying plan
        await Planner(ioc).apply_plan(plan)

        tasks.add(asyncio.create_task(scheduler.run(stop_event), name="scheduler_task"))
        tasks.add(asyncio.create_task(stop_event.wait(), name="stop_event_wait"))

        # Ready to serve
        service_ready.set()
        logger.warning("Service started, waiting for termination signal")
        await wait_tasks_shutdown()
        logger.info("Bye!")


if __name__ == "__main__":
    if sys.version_info >= (3, 11):
        with asyncio.Runner(loop_factory=uvloop.new_event_loop) as runner:
            runner.run(main(runner.get_loop()))
    else:
        event_loop = uvloop.new_event_loop()
        event_loop.run_until_complete(main(event_loop))
