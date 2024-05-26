from __future__ import annotations

import inspect
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Awaitable, Callable, Protocol

import structlog
from pydantic import BaseModel
from zoneinfo import ZoneInfo

from ..hue.v1.models import Scene
from .context import Context
from .serializable import Serializable

logger = structlog.getLogger(__name__)

# - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -


class EvaluatedAction(Protocol):
    def __call__(self) -> Awaitable[None]: ...


class PlanAction(Protocol):
    async def define_action(self, context: Context) -> EvaluatedAction: ...

    def chain(self, other: PlanAction) -> PlanAction:
        return PlanActionSequence(self, other)

    def if_(self, cond: Callable[[], bool] | Callable[[], Awaitable[bool]]) -> PlanAction:
        return PlanActionWithRuntimeCondition(cond, self)

    def with_callback(
        self, callback: Callable[..., None] | Callable[..., Awaitable[None]], *args, **kwargs
    ) -> PlanAction:
        return PlanActionSequence(self, PlanActionCallback(callback, *args, **kwargs))


# - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -


class PlanActionSequence(PlanAction):
    def __init__(self, *actions) -> None:
        super().__init__()
        self._actions: tuple[PlanAction, ...] = tuple(item for a in actions for item in self._unpack_nested_sequence(a))

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(items=[" + ", ".join(repr(i) for i in self._actions) + "])"

    def _unpack_nested_sequence(self, action: PlanAction) -> tuple[PlanAction, ...]:
        if isinstance(action, PlanActionSequence):
            return action._actions
        return (action,)

    async def define_action(self, context: Context) -> EvaluatedAction:
        evaluated_actions: list[EvaluatedAction] = []
        for action in self._actions:
            evaluated_action = await action.define_action(context=context)
            evaluated_actions.append(evaluated_action)

        async def sequence_evaluated_action():
            for evaluated_action in evaluated_actions:
                await evaluated_action()

        return sequence_evaluated_action


# - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -


class PlanActionWithEvaluationCondition(PlanAction):
    def __init__(self, condition: Callable[[], bool] | Callable[[], Awaitable[bool]], action: PlanAction) -> None:
        super().__init__()
        self._action: PlanAction = action
        self._condition = condition

    async def define_action(self, context: Context) -> EvaluatedAction:
        async def _action():
            logger.info("Empty action executed (evaluation condition not match)")

        if inspect.iscoroutinefunction(self._condition):
            satisfied = await self._condition()  # Await if it's awaitable
        else:
            satisfied = self._condition()  # Call directly if it's not awaitable

        if satisfied:
            _action = await self._action.define_action(context)  # type: ignore
        else:
            logger.info("Action not evaluated because evaluation condition not match")

        return _action


class PlanActionWithRuntimeCondition(PlanAction):
    def __init__(self, condition: Callable[[], bool] | Callable[[], Awaitable[bool]], action: PlanAction) -> None:
        super().__init__()
        self._action: PlanAction = action
        self._condition = condition

    async def define_action(self, context: Context) -> EvaluatedAction:
        _action = await self._action.define_action(context)

        async def action():
            if inspect.iscoroutinefunction(self._condition):
                satisfied = await self._condition()  # Await if it's awaitable
            else:
                satisfied = self._condition()  # Call directly if it's not awaitable

            if satisfied:
                return await _action()
            else:
                logger.info("Action not executed because runtime condition not match")

        return action


# - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -


class PlanActionCallback(PlanAction):
    def __init__(self, callback: Callable[..., None] | Callable[..., Awaitable[None]], *args, **kwargs) -> None:
        super().__init__()
        self._callback = callback
        self._args = args
        self._kwargs = kwargs

    async def define_action(self, context: Context) -> EvaluatedAction:
        async def action():
            if inspect.iscoroutinefunction(self._callback):
                await self._callback(*self._args, **self._kwargs)  # Await if it's awaitable
            else:
                self._callback(*self._args, **self._kwargs)  # Call directly if it's not awaitable

        return action


# - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -


@dataclass(kw_only=True)
class PlanActionStoreScene(PlanAction, Protocol):
    store_as: str
    activate: bool = True
 
    async def define_action(self, context: Context) -> EvaluatedAction:
        required_scene = None
        for scene in await context.hue_client_v1.get_scenes():
            if self.match_scene(scene):
                required_scene = scene.model_copy()  # ensure we don't loose model in closure below
                logger.info("Found required scene", scene=repr(required_scene), action=repr(self))
                break
        else:
            raise ValueError("Required scene not found")

        async def set_scene():
            await context.scenes.set(self.store_as, required_scene)
            log = logger.bind(scene_id=required_scene.id, scene_name=required_scene.name)
            log.debug("Context current scene set to", scene=required_scene)
            if self.activate:
                group = await context.hue_client_v1.get_group(scene.group)
                if not group.state.any_on:
                    log.info("Scene not activated, because group is not active", group_id=group.id, group_state=group.state)
                    return
                res = await context.hue_client_v1.activate_scene(required_scene.group, required_scene.id)
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

    def match_scene(self, scene: Scene) -> bool:
        return scene.id == self.id


# - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -


@dataclass
class PlanActionToggleStoredScene(PlanAction, Serializable):
    stored_scene: str
    fallback_nearest_scheduler_job_tag: str | None = None

    class _Model(BaseModel):
        stored_scene: str
        fallback_nearest_scheduler_job_tag: str | None = None

    @staticmethod
    async def run_nearest_scheduled_job(context: Context, tag: str):
        logger.debug("Looking for nearest previous job")
        prev_job = await context.scheduler.previous_closest_job(tags={tag})
        if prev_job is not None:
            logger.info("Found closest previous job", job=prev_job)
        else:
            logger.warning("No previous closest job available by time")

        next_job = await context.scheduler.next_closest_job(tags={tag})
        if next_job is not None:
            logger.info("Found closest next job", job=next_job)
        else:
            logger.warning("No next closest job available by time")

        job = prev_job if prev_job else next_job
        if not job:
            # If both are unavailable, log error and return
            logger.error("No closest jobs available")
            return
        logger.debug("Executing closest job to current time (off schedule)", job=job)
        await job.execute(off_schedule=True)

    async def define_action(self, context: Context) -> EvaluatedAction:
        async def toggle_current_scene():
            scene = await context.scenes.get(self.stored_scene)
            if not scene:
                if self.fallback_nearest_scheduler_job_tag:
                    logger.debug(
                        "No current scene stored, performing fallback procedure",
                        fallback_nearest_scheduler_job_tag=self.fallback_nearest_scheduler_job_tag,
                    )
                    await self.run_nearest_scheduled_job(context=context, tag=self.fallback_nearest_scheduler_job_tag)
                scene = await context.scenes.get(self.stored_scene)
            if not scene:
                logger.error("Can't toggle scene, because it was not set yet")
                return
            logger.debug(
                "Context current scene obtained",
                stored_scene_id=self.stored_scene,
                scene=scene,
            )
            group = await context.hue_client_v1.get_group(scene.group)
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
            result = await context.hue_client_v1.send_group_action(scene.group, action)
            logger.debug("Scene toggled", result=result)

        return toggle_current_scene
