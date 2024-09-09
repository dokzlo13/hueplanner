from __future__ import annotations

from dataclasses import dataclass, field
from datetime import time, timedelta, datetime, tzinfo
from typing import Annotated

import pytimeparse
import structlog
from pydantic import BaseModel
from pydantic.functional_validators import BeforeValidator

from hueplanner.planner.actions import EvaluatedAction
from hueplanner.planner.serializable import Serializable
from hueplanner.time_parser import TimeParser
from hueplanner.scheduler import Scheduler
from hueplanner.storage.interface import IKeyValueStorage

from .interface import PlanTrigger

logger = structlog.getLogger(__name__)


def parse_timedelta(value: str) -> timedelta:
    return timedelta(seconds=pytimeparse.parse(value))  # type: ignore


@dataclass(kw_only=True)
class PlanTriggerOnce(PlanTrigger, Serializable):
    act_on: str
    alias: str | None = None
    scheduler_tag: str | None = None
    variables_db: list[str] = field(default_factory=list)

    class _Model(BaseModel):
        act_on: str
        alias: str | None = None
        scheduler_tag: str | None = None
        variables_db: list[str] = []

    async def apply_trigger(self, action: EvaluatedAction, scheduler: Scheduler, storage: IKeyValueStorage, tz: tzinfo):
        variables_collections = []
        for variables_db in self.variables_db:
            variables_collections.append(await storage.create_collection(variables_db))

        alias = self.alias if self.alias is not None else f"task:'{str(self.act_on)}'"
        act_on_time = (await TimeParser(tz, variables_collections).parse(self.act_on)).timetz()
        logger.debug("Applying once trigger", act_on=str(self.act_on), act_on_time=act_on_time)

        scheduler.once(
            coro=action,
            run_at=act_on_time,
            alias=alias,
            tags={self.scheduler_tag} if self.scheduler_tag is not None else None,
        )


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
        # start_at = self.start_at
        # if start_at is None:
        #     start_at = (datetime.now(tz) + self.interval).time()  # TODO: provide tz
        variables_collections = []
        for variables_db in self.variables_db:
            variables_collections.append(await storage.create_collection(variables_db))

        start_at = None
        if self.start_at:
            start_at = (await TimeParser(tz, variables_collections).parse(self.start_at)).timetz()

        logger.info("Applying periodic trigger", interval=str(self.interval), start_at=str(start_at))
        scheduler.periodic(action, interval=self.interval, start_at=start_at, alias=self.alias)
