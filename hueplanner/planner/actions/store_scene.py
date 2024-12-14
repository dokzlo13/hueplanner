from __future__ import annotations

from typing import Protocol

import structlog
from pydantic.dataclasses import dataclass

from hueplanner.hue.v1 import HueBridgeV1
from hueplanner.hue.v1.models import Scene as SceneV1
from hueplanner.hue.v2 import HueBridgeV2
from hueplanner.hue.v2.models import Scene as SceneV2
from hueplanner.planner.serializable import Serializable
from hueplanner.storage.interface import IKeyValueStorage

from .common import derive_v2_db_name
from .interface import EvaluatedAction, PlanAction

logger = structlog.getLogger(__name__)


@dataclass(kw_only=True)
class PlanActionStoreScene(PlanAction, Protocol):
    db_key: str
    db: str = "stored_scenes"
    activate: bool = True

    async def define_action(
        self,
        hue_v1: HueBridgeV1,
        hue_v2: HueBridgeV2,
        storage: IKeyValueStorage,
    ) -> EvaluatedAction:
        scenes_v1 = await storage.create_collection(self.db)
        scenes_v2 = await storage.create_collection(derive_v2_db_name(self.db))

        required_scene_v1 = None
        required_scene_v2 = None

        for scene in await hue_v1.get_scenes():
            if self.match_scene(scene):
                required_scene_v1 = scene.model_copy()  # ensure we don't loose model in closure below
                break
        else:
            raise ValueError("Required scene (v1) not found")

        for scene in await hue_v2.get_scenes():
            if await self.match_scene_v2(hue_v2, scene):
                required_scene_v2 = scene.model_copy()  # ensure we don't loose model in closure below
                break
        else:
            raise ValueError("Required scene (v2) not found")

        async def set_scene():
            logger.info("Storing scene requested", action=repr(self))
            await scenes_v1.set(self.db_key, required_scene_v1)
            await scenes_v2.set(self.db_key, required_scene_v2)

            log = logger.bind(
                scene_id=required_scene_v1.id,
                scene_id_v2=required_scene_v2.id,
                scene_name=required_scene_v1.name,
            )
            log.debug("Context current scene set to", scene_v1=required_scene_v1, scene_v2=required_scene_v2)

            # FIXME: Failed SRP here
            if self.activate:
                group = await hue_v1.get_group(required_scene_v1.group)
                if not group.state.any_on:
                    log.info(
                        "Scene not activated, because group is not active", group_id=group.id, group_state=group.state
                    )
                    return
                res = await hue_v1.activate_scene(required_scene_v1.group, required_scene_v1.id)
                log.info("Scene activated", res=res)

        logger.info(
            "Store scene action prepared",
            scene=repr(required_scene_v1.id),
            scene_id_v2=required_scene_v2.id,
            action=repr(self),
        )
        return set_scene

    def match_scene(self, scene: SceneV1) -> bool: ...

    async def match_scene_v2(self, hue_v2: HueBridgeV2, scene: SceneV2) -> bool: ...


@dataclass(kw_only=True)
class PlanActionStoreSceneByName(PlanActionStoreScene, Serializable):
    name: str
    group: int | None = None

    def match_scene(self, scene: SceneV1) -> bool:
        if scene.name == self.name:
            if not self.group:
                return True
            if scene.group == self.group:
                return True
        return False

    async def match_scene_v2(self, hue_v2: HueBridgeV2, scene: SceneV2) -> bool:
        if scene.metadata.name == self.name:
            if not self.group:
                return True
            group = await hue_v2.get_zone(scene.group.rid)
            if not group.id_v1:
                return False
            if str(group.id_v1.split("/groups/")[-1]).lower() == str(self.group).lower():
                return True
        return False


@dataclass(kw_only=True)
class PlanActionStoreSceneById(PlanActionStoreScene, Serializable):
    id: str

    def match_scene(self, scene: SceneV1) -> bool:
        return scene.id == self.id

    async def match_scene_v2(self, hue_v2: HueBridgeV2, scene: SceneV2) -> bool:
        if not scene.id_v1:
            return False
        return scene.id_v1.split("/scenes/")[-1] == self.id
