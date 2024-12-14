from __future__ import annotations

import structlog
from pydantic.dataclasses import dataclass

from hueplanner.hue.v2 import HueBridgeV2
from hueplanner.hue.v2.models import Light, Scene, SceneActionData
from hueplanner.planner.serializable import Serializable
from hueplanner.storage.interface import IKeyValueStorage

from .common import derive_v2_db_name
from .interface import EvaluatedAction, PlanAction

logger = structlog.getLogger(__name__)


@dataclass(kw_only=True)
class PlanActionSyncScene(PlanAction, Serializable):
    db_key: str
    db: str = "stored_scenes"

    @staticmethod
    def scene_action_differs(logger, light: Light, action_data: SceneActionData) -> bool:
        BRIGHTNESS_TOLERANCE = 0.5
        COLOR_TOLERANCE = 0.0001

        # Compare on/off
        if action_data.on is not None:
            light_is_on = light.dimming is not None and light.dimming.brightness > 0
            required_on = action_data.on.on
            if required_on and not light_is_on:
                logger.debug(
                    "Light differs: on state",
                    required=required_on,
                    current=light_is_on,
                    reason="Light should be on but is off",
                )
                return True
            if not required_on and light_is_on:
                logger.debug(
                    "Light differs: on state",
                    required=required_on,
                    current=light_is_on,
                    reason="Light should be off but is on",
                )
                return True

        # Compare dimming (with tolerance)
        if action_data.dimming is not None:
            required_brightness = action_data.dimming.brightness
            current_brightness = light.dimming.brightness  # type: ignore
            if abs(required_brightness - current_brightness) > BRIGHTNESS_TOLERANCE:
                logger.debug(
                    "Light differs: brightness",
                    required=required_brightness,
                    current=current_brightness,
                    tolerance=BRIGHTNESS_TOLERANCE,
                )
                return True

        # Compare color temperature (ignore mirek_valid, mirek_schema)
        if action_data.color_temperature is not None:
            required_mirek = action_data.color_temperature.mirek
            current_mirek = light.color_temperature.mirek
            if required_mirek != current_mirek:
                logger.debug("Light differs: mirek", required=required_mirek, current=current_mirek)
                return True

        # Compare color (xy)
        if action_data.color is not None and action_data.color.xy is not None:
            required_x = action_data.color.xy.x
            required_y = action_data.color.xy.y
            current_x = light.color.xy.x  # type: ignore
            current_y = light.color.xy.y  # type: ignore
            if abs(required_x - current_x) > COLOR_TOLERANCE or abs(required_y - current_y) > COLOR_TOLERANCE:
                logger.debug(
                    "Light differs: color xy",
                    required_x=required_x,
                    required_y=required_y,
                    current_x=current_x,
                    current_y=current_y,
                    tolerance=COLOR_TOLERANCE,
                )
                return True

        # Compare gradient
        if action_data.gradient is not None:
            logger.debug("Light differs: gradient set but not in light", required=str(action_data.gradient))
            return True

        # Compare effects
        if action_data.effects is not None:
            logger.debug("Light differs: effects set but not in light", required=str(action_data.effects))
            return True

        # Compare dynamics
        if action_data.dynamics is not None:
            logger.debug("Light differs: dynamics set but not in light", required=str(action_data.dynamics))
            return True

        # If we reach here, no differences found
        return False

    async def define_action(self, storage: IKeyValueStorage, hue_v2: HueBridgeV2) -> EvaluatedAction:
        async def toggle_current_scene():
            logger.info("Scene sync requested", action=repr(self))

            scenes_v2 = await storage.create_collection(derive_v2_db_name(self.db))
            scene_v2: Scene | None = await scenes_v2.get(self.db_key)

            if not scene_v2:
                logger.warning("Can't sync scene, because it was not set yet")
                return
            logger.debug("Context current scene obtained", stored_scene_id=self.db_key, scene_v2=scene_v2)

            for targeted_action in scene_v2.actions:
                light = await hue_v2.get_light(targeted_action.target.rid)
                log = logger.bind(id_v1=light.id_v1, id_v2=light.id, name=light.metadata.name)

                log.debug("Testing light")
                if self.scene_action_differs(log, light, targeted_action.action):
                    update = targeted_action.action.as_light_update_request()
                    log.info("Light differs from required, performing update", update=update)
                    res = await hue_v2.update_light(targeted_action.target.rid, update)
                    log.info("Light updated", res=res)
                else:
                    log.debug("No update required for light")

            logger.info("Scene sync performed", action=repr(self))

        return toggle_current_scene
