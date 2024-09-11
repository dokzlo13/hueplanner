from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, time, timedelta, tzinfo
from typing import Annotated, Protocol

import pytimeparse2 as pytimeparse
import structlog
from pydantic import BaseModel
from pydantic.functional_validators import BeforeValidator

from hueplanner.planner.actions import EvaluatedAction
from hueplanner.planner.serializable import Serializable
from hueplanner.scheduler import Scheduler
from hueplanner.storage.interface import IKeyValueStorage
from hueplanner.time_parser import TimeParser

from .interface import PlanTrigger

logger = structlog.getLogger(__name__)


def parse_timedelta(value: str) -> timedelta:
    return timedelta(seconds=pytimeparse.parse(value))  # type: ignore


@dataclass(kw_only=True)
class PlanTriggerOnce(PlanTrigger, Serializable):
    time: str
    alias: str | None = None
    scheduler_tag: str | None = None
    variables_db: list[str] = field(default_factory=list)
    shift_if_late: bool = False

    class _Model(BaseModel):
        time: str
        alias: str | None = None
        scheduler_tag: str | None = None
        variables_db: list[str] = []
        shift_if_late: bool = False

    async def apply_trigger(self, action: EvaluatedAction, scheduler: Scheduler, storage: IKeyValueStorage, tz: tzinfo):
        variables_collections = []
        for variables_db in self.variables_db:
            variables_collections.append(await storage.create_collection(variables_db))

        alias = self.alias if self.alias is not None else f"{self.time}"
        act_on_time = (await TimeParser(tz, variables_collections).parse(self.time)).timetz()

        task = scheduler.once(
            coro=action,
            run_at=act_on_time,
            alias=alias,
            tags={self.scheduler_tag} if self.scheduler_tag is not None else None,
            shift_if_late=self.shift_if_late,
        )
        logger.info("Once trigger added to schedule", schedule=task.schedule)


@dataclass
class PlanTriggerPeriodic(PlanTrigger, Serializable):
    interval: timedelta
    start_at: str | None = None
    alias: str | None = None
    variables_db: list[str] = field(default_factory=list)

    class _Model(BaseModel):
        interval: Annotated[timedelta, BeforeValidator(parse_timedelta)]
        start_at: str | None = None
        alias: str | None = None
        variables_db: list[str] = []

    async def apply_trigger(self, action: EvaluatedAction, scheduler: Scheduler, storage: IKeyValueStorage, tz: tzinfo):
        variables_collections = []
        for variables_db in self.variables_db:
            variables_collections.append(await storage.create_collection(variables_db))

        start_at = None
        if self.start_at:
            start_at = (await TimeParser(tz, variables_collections).parse(self.start_at)).timetz()

        alias = (
            self.alias
            if self.alias is not None
            else (
                f"each {self.interval} since "
                f"{self.start_at if self.start_at else start_at.isoformat(timespec='seconds')}"
            )
        )
        task = scheduler.periodic(action, interval=self.interval, start_at=start_at, alias=alias)
        logger.info("Periodic trigger added to schedule", schedule=task.schedule, action=action)


@dataclass(kw_only=True)
class _PlanTriggerConvenientPeriodic(PlanTrigger, Serializable, Protocol):
    alias: str | None = None
    scheduler_tag: str | None = None

    class _Model(BaseModel):
        alias: str | None = None
        scheduler_tag: str | None = None

    async def _calculate_params(self, storage: IKeyValueStorage, tz: tzinfo) -> tuple[time, timedelta]: ...

    async def apply_trigger(self, action: EvaluatedAction, scheduler: Scheduler, storage: IKeyValueStorage, tz: tzinfo):

        start_at, interval = await self._calculate_params(storage, tz)
        alias = (
            self.alias if self.alias is not None else f"each {interval} since {start_at.isoformat(timespec='seconds')}"
        )

        task = scheduler.periodic(action, interval=interval, start_at=start_at, alias=alias)
        logger.info("Periodic trigger added to schedule", schedule=task.schedule, action=action)


@dataclass(kw_only=True)
class PlanTriggerDaily(_PlanTriggerConvenientPeriodic):
    time: str | None = None
    variables_db: list[str] = field(default_factory=list)

    class _Model(BaseModel):
        time: str | None = None
        alias: str | None = None
        scheduler_tag: str | None = None
        variables_db: list[str] = []

    async def _calculate_params(self, storage: IKeyValueStorage, tz: tzinfo) -> tuple[time, timedelta]:
        if self.time is None:
            return (datetime.now(tz) + timedelta(days=1)).time(), timedelta(days=1)

        variables_collections = []
        for variables_db in self.variables_db:
            variables_collections.append(await storage.create_collection(variables_db))

        start_at = (await TimeParser(tz, variables_collections).parse(self.time)).timetz()

        return start_at, timedelta(days=1)


@dataclass(kw_only=True)
class PlanTriggerMinutely(_PlanTriggerConvenientPeriodic):
    async def _calculate_params(self, storage: IKeyValueStorage, tz: tzinfo) -> tuple[time, timedelta]:
        return (datetime.now(tz) + timedelta(minutes=1)).time(), timedelta(minutes=1)


@dataclass(kw_only=True)
class PlanTriggerHourly(_PlanTriggerConvenientPeriodic):
    async def _calculate_params(self, storage: IKeyValueStorage, tz: tzinfo) -> tuple[time, timedelta]:
        return (datetime.now(tz) + timedelta(hours=1)).time(), timedelta(hours=1)
