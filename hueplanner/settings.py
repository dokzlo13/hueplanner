import os
import typing

import environs
import structlog

logger = structlog.getLogger(__name__)


class Env(environs.Env):
    @staticmethod
    def read_env(
        path: typing.Optional[str] = None,
        recurse: bool = True,
        verbose: bool = False,
        override: bool = False,
    ) -> None:
        env_files = ("settings.cfg", ".env")
        for env_file in env_files:
            if os.path.isfile(env_file):
                path = env_file
                logger.info(f"Loading settings file: {path}")
                return environs.Env.read_env(path, recurse, verbose, override)

        logger.warning("Settings file not found! Using the default values")
        return environs.Env.read_env(path, recurse, verbose, override)


env = Env()
env.read_env()

LOG_LEVEL = env("LOG_LEVEL", "info")
LOG_COLORS = env.bool("LOG_COLORS", True)

HUE_BRIDGE_ADDR = env("HUE_BRIDGE_ADDR")
HUE_BRIDGE_USERNAME = env("HUE_BRIDGE_USERNAME")

GEO_LOCATION_NAME = env("GEO_LOCATION_NAME")

PRINT_SCHEDULE_INTERVAL = env.int("PRINT_SCHEDULE_INTERVAL", 0)

# TODO: health check
HEALTHCHECK_SERVER_HOST = env("HEALTHCHECK_SERVER_HOST", "0.0.0.0")
HEALTHCHECK_SERVER_PORT = env.int("HEALTHCHECK_SERVER_PORT", 9090)
