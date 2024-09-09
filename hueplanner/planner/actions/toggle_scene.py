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
    stored_scene: str
    fallback_nearest_task_tag: str | None = None
    target_db: str = "stored_scenes"

    class _Model(BaseModel):
        stored_scene: str
        fallback_nearest_task_tag: str | None = None

    @staticmethod
    async def run_nearest_scheduled_task(tag: str, scheduler: Scheduler):
        logger.debug("Looking for nearest previous task")
        prev_task = scheduler.previous_closest_task(tags={tag})
        if prev_task is not None:
            logger.info("Found closest previous task", task=prev_task)
        else:
            logger.warning("No previous closest task available by time")

        next_task = scheduler.next_closest_task(tags={tag})
        if next_task is not None:
            logger.info("Found closest next task", task=next_task)
        else:
            logger.warning("No next closest task available by time")

        task = prev_task if prev_task else next_task
        if not task:
            # If both are unavailable, log error and return
            logger.error("No closest tasks available")
            return

        logger.debug("Executing closest task to current time (off schedule)", task=task)
        await task.execute()

    async def define_action(
        self,
        storage: IKeyValueStorage,
        scheduler: Scheduler,
        hue_v1: HueBridgeV1,
    ) -> EvaluatedAction:
        async def toggle_current_scene():
            scenes = await storage.create_collection(self.target_db)

            scene = await scenes.get(self.stored_scene)
            if not scene:
                if self.fallback_nearest_task_tag:
                    logger.debug(
                        "No current scene stored, performing fallback procedure",
                        fallback_nearest_task_tag=self.fallback_nearest_task_tag,
                    )
                    await self.run_nearest_scheduled_task(scheduler=scheduler, tag=self.fallback_nearest_task_tag)
                scene = await scenes.get(self.stored_scene)
            if not scene:
                logger.error("Can't toggle scene, because it was not set yet")
                return
            logger.debug(
                "Context current scene obtained",
                stored_scene_id=self.stored_scene,
                scene=scene,
            )
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
