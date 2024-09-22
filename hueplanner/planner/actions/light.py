from __future__ import annotations

import structlog
from aiohttp import client_exceptions
from pydantic.dataclasses import dataclass

from hueplanner.hue.v2 import HueBridgeV2
from hueplanner.hue.v2.models.light import LightUpdateRequest
from hueplanner.planner.serializable import Serializable

from .interface import EvaluatedAction, PlanAction

logger = structlog.getLogger(__name__)


@dataclass(kw_only=True)
class PlanActionUpdateLightV2(PlanAction, Serializable):
    id: str
    update: LightUpdateRequest

    async def define_action(self) -> EvaluatedAction:
        async def update_light(hue_v2: HueBridgeV2):
            logger.info("Light update requested", action=repr(self))

            try:
                response = await hue_v2.update_light(id=self.id, update=self.update)
            except client_exceptions.ClientResponseError:
                logger.exception("Failed to update light")
            logger.info("Light updated", response=repr(response))

        return update_light
