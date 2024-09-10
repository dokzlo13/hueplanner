from __future__ import annotations

from dataclasses import dataclass

from aiohttp import client_exceptions
import structlog
from pydantic import BaseModel

from hueplanner.hue.v1 import HueBridgeV1
from hueplanner.hue.v2 import HueBridgeV2
from hueplanner.hue.v2.models.light import LightUpdateRequest

from hueplanner.planner.serializable import Serializable
from hueplanner.scheduler import Scheduler
from hueplanner.storage.interface import IKeyValueStorage

from .interface import EvaluatedAction, PlanAction

logger = structlog.getLogger(__name__)


@dataclass(kw_only=True)
class PlanActionUpdateLightV2(PlanAction, Serializable):
    id: str
    update: LightUpdateRequest

    class _Model(BaseModel):
        id: str
        update: LightUpdateRequest

    def __post_init__(self):
        # TODO: serializable should pass correct type without this hack (currently passes dict)
        self.update = LightUpdateRequest.model_validate(self.update)

    async def define_action(self) -> EvaluatedAction:
        print("\n\nupdate:", repr(self.update), type(self.update))

        async def update_light(hue_v2: HueBridgeV2):
            logger.info("Light update requested", action=repr(self))

            try:
                response = await hue_v2.update_light(id=self.id, update=self.update)
            except client_exceptions.ClientResponseError:
                logger.exception("Failed to update light")
            logger.info("Light updated", response=repr(response))

        return update_light
