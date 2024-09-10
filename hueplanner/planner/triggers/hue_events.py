from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

import structlog
from pydantic import BaseModel

from hueplanner.event_listener import HueEventStreamListener
from hueplanner.hue.v2.models import HueEvent
from hueplanner.planner.actions import EvaluatedAction
from hueplanner.planner.serializable import Serializable

from .interface import PlanTrigger

logger = structlog.getLogger(__name__)


@dataclass
class PlanTriggerOnHueEvent(PlanTrigger, Protocol):
    async def apply_trigger(self, action: EvaluatedAction, stream_listener: HueEventStreamListener):
        async def cb_action(_: HueEvent) -> None:
            logger.info("Hue event matched requirements, executing action", trigger=repr(self))
            return await action()

        stream_listener.register_callback(self._check, cb_action)
        logger.info("Registered HueEventStream event listener", trigger=repr(self))

    async def _check(self, hevent: HueEvent) -> bool: ...


@dataclass
class PlanTriggerOnHueButtonEvent(PlanTriggerOnHueEvent, Serializable):
    resource_id: str
    action: str

    class _Model(BaseModel):
        resource_id: str
        action: str

    def __post_init__(self):
        if self.resource_id == "" or self.action == "":
            raise ValueError("Fields 'resource_id' and 'action' cannot be empty")

    async def _check(self, hevent: HueEvent) -> bool:
        for event in hevent.data:
            for data in event["data"]:
                if data["id"] == self.resource_id and data["type"] == "button":
                    report = data[data["type"]]["button_report"]
                    if report["event"] == self.action:
                        return True
        return False
