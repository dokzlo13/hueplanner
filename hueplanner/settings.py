# import os
# import typing

# import environs
# import structlog

# logger = structlog.getLogger(__name__)


# class Env(environs.Env):
#     @staticmethod
#     def read_env(
#         path: typing.Optional[str] = None,
#         recurse: bool = True,
#         verbose: bool = False,
#         override: bool = False,
#     ) -> None:
#         env_files = (".env", "settings.cfg")
#         for env_file in env_files:
#             if os.path.isfile(env_file):
#                 path = env_file
#                 logger.info(f"Loading settings file: {path}")
#                 return environs.Env.read_env(path, recurse, verbose, override)

#         logger.warning("Settings file not found! Using the default values")
#         return environs.Env.read_env(path, recurse, verbose, override)


# env = Env()
# env.read_env()

# LOG_LEVEL = env("LOG_LEVEL", "info")
# LOG_COLORS = env.bool("LOG_COLORS", True)

# HUE_BRIDGE_ADDR = env("HUE_BRIDGE_ADDR")
# HUE_BRIDGE_USERNAME = env("HUE_BRIDGE_USERNAME")

# GEO_LOCATION_NAME = env("GEO_LOCATION_NAME")

# PRINT_SCHEDULE_INTERVAL = env.int("PRINT_SCHEDULE_INTERVAL", 0)

# DATABASE_PATH = env("DATABASE_PATH", None)

# # TODO: health check
# HEALTHCHECK_SERVER_HOST = env("HEALTHCHECK_SERVER_HOST", "0.0.0.0")
# HEALTHCHECK_SERVER_PORT = env.int("HEALTHCHECK_SERVER_PORT", 9090)


from typing import Annotated, Any, Tuple, Type

from pydantic import Field, GetCoreSchemaHandler
from pydantic_core import core_schema
from pydantic_settings import (
    BaseSettings,
    PydanticBaseSettingsSource,
    SettingsConfigDict,
    YamlConfigSettingsSource,
)
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


class _ZoneInfoPydanticAnnotation:
    @classmethod
    def __get_pydantic_core_schema__(cls, _source_type: Any, _handler: GetCoreSchemaHandler) -> core_schema.CoreSchema:
        def validate_from_str(value: str) -> ZoneInfo:
            try:
                return ZoneInfo(value)
            except ZoneInfoNotFoundError:
                raise ValueError("Invalid timezone")

        from_str_schema = core_schema.chain_schema(
            [
                core_schema.str_schema(),
                core_schema.no_info_plain_validator_function(validate_from_str),
            ]
        )
        return core_schema.json_or_python_schema(
            json_schema=from_str_schema,
            python_schema=core_schema.union_schema(
                [
                    # check if it's an instance first before doing any further work
                    core_schema.is_instance_schema(ZoneInfo),
                    from_str_schema,
                ]
            ),
            serialization=core_schema.plain_serializer_function_ser_schema(
                lambda instance: str(instance), when_used="json"
            ),
        )


TimezoneInfo = Annotated[ZoneInfo, _ZoneInfoPydanticAnnotation]


class LogSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="log_", extra="ignore")

    level: str = "info"
    colors: bool = True


class HueBridgeSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="hue_bridge_", extra="ignore")

    addr: str
    username: str


class DatabaseSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="database_", extra="ignore")

    path: str | None = None


class HealthCheckSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="healthcheck_", extra="ignore")

    host: str = "0.0.0.0"
    port: int = 9090


class Settings(BaseSettings):
    model_config = SettingsConfigDict(extra="ignore")

    log: LogSettings = Field(default_factory=LogSettings)
    hue_bridge: HueBridgeSettings = Field(default_factory=HueBridgeSettings)  # type: ignore
    database: DatabaseSettings = Field(default_factory=DatabaseSettings)
    healthcheck: HealthCheckSettings | None = Field(default=None)

    tz: TimezoneInfo | None = Field(default=None)


class _ConfigSettings(BaseSettings):
    model_config = SettingsConfigDict(extra="ignore")

    settings: Settings = Field(default_factory=Settings)

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: Type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> Tuple[PydanticBaseSettingsSource, ...]:
        return (
            init_settings,
            YamlConfigSettingsSource(settings_cls),
            env_settings,
            dotenv_settings,
        )


def load_settings(path: str) -> Settings:
    _ConfigSettings.model_config["yaml_file"] = path
    return _ConfigSettings().settings
