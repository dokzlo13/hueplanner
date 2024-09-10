from __future__ import annotations

from dataclasses import dataclass

import structlog
from pydantic import BaseModel

from hueplanner.hue.v1 import HueBridgeV1
from hueplanner.planner.serializable import Serializable
from hueplanner.scheduler import Scheduler
from hueplanner.storage.interface import IKeyValueStorage

from .interface import EvaluatedAction, PlanAction

logger = structlog.getLogger(__name__)


@dataclass(kw_only=True)
class PlanActionToggleStoredScene(PlanAction, Serializable):
    db_key: str
    target_db: str = "stored_scenes"

    class _Model(BaseModel):
        db_key: str

    async def define_action(
        self,
        storage: IKeyValueStorage,
        scheduler: Scheduler,
        hue_v1: HueBridgeV1,
    ) -> EvaluatedAction:
        async def toggle_current_scene():
            logger.info("Scene toggling requested", action=repr(self))

            scenes = await storage.create_collection(self.target_db)
            scene = await scenes.get(self.db_key)
            if not scene:
                logger.warning("Can't toggle scene, because it was not set yet")
                return
            logger.debug("Context current scene obtained", stored_scene_id=self.db_key, scene=scene)
            group = await hue_v1.get_group(scene.group)
            logger.debug("Current group state", group_id=group.id, group_state=group.state)

            # TODO: Better typing - use models, not dict
            if group.state.all_on:
                action = {"on": False}
                logger.info("Turning light off", group=scene.group)
            else:
                logger.info(
                    "Turning light on and setting scene",
                    group=scene.group,
                    scene_id=scene.id,
                    scene_name=scene.name,
                )
                action = {"on": True, "scene": scene.id}
            result = await hue_v1.send_group_action(scene.group, action)
            logger.debug("Scene toggled", result=result)

        return toggle_current_scene
