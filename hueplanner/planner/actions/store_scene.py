from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

import structlog
from pydantic import BaseModel

from hueplanner.hue.v1 import HueBridgeV1
from hueplanner.hue.v1.models import Scene
from hueplanner.planner.serializable import Serializable
from hueplanner.storage.interface import IKeyValueStorage

from .interface import EvaluatedAction, PlanAction

logger = structlog.getLogger(__name__)


@dataclass(kw_only=True)
class PlanActionStoreScene(PlanAction, Protocol):
    store_as: str
    activate: bool = True
    target_collection: str = "stored_scenes"

    async def define_action(self, hue_v1: HueBridgeV1, storage: IKeyValueStorage) -> EvaluatedAction:
        scenes = await storage.create_collection(self.target_collection)

        required_scene = None
        for scene in await hue_v1.get_scenes():
            if self.match_scene(scene):
                required_scene = scene.model_copy()  # ensure we don't loose model in closure below
                logger.info("Found required scene", scene=repr(required_scene), action=repr(self))
                break
        else:
            raise ValueError("Required scene not found")

        async def set_scene():
            await scenes.set(self.store_as, required_scene)
            log = logger.bind(scene_id=required_scene.id, scene_name=required_scene.name)
            log.debug("Context current scene set to", scene=required_scene)
            if self.activate:
                group = await hue_v1.get_group(scene.group)
                if not group.state.any_on:
                    log.info(
                        "Scene not activated, because group is not active", group_id=group.id, group_state=group.state
                    )
                    return
                res = await hue_v1.activate_scene(required_scene.group, required_scene.id)
                log.info("Scene activated", res=res)

        return set_scene

    def match_scene(self, scene: Scene) -> bool: ...


@dataclass(kw_only=True)
class PlanActionStoreSceneByName(PlanActionStoreScene, Serializable):
    name: str
    group: int | None = None

    class _Model(BaseModel):
        store_as: str
        name: str
        group: int | None = None
        target_collection: str = "stored_scenes"

    def match_scene(self, scene: Scene) -> bool:
        if scene.name == self.name:
            if not self.group:
                return True
            if scene.group == self.group:
                return True
        return False


@dataclass(kw_only=True)
class PlanActionStoreSceneById(PlanActionStoreScene, Serializable):
    id: str

    class _Model(BaseModel):
        store_as: str
        id: str
        target_collection: str = "stored_scenes"

    def match_scene(self, scene: Scene) -> bool:
        return scene.id == self.id
