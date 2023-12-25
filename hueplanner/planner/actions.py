from __future__ import annotations

import inspect
from dataclasses import dataclass
from typing import Awaitable, Callable, Protocol

import structlog

from ..hue.v1.models import Scene
from .context import Context

logger = structlog.getLogger(__name__)

# - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -


class EvaluatedAction(Protocol):
    def __call__(self) -> Awaitable[None]:
        ...


class PlanAction(Protocol):
    async def define_action(self, context: Context) -> EvaluatedAction:
        ...

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
        self._actions: tuple[PlanAction, ...] = actions

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


@dataclass
class PlanActionActivateScene(PlanAction, Protocol):
    transition_time: int | None = None

    async def define_action(self, context: Context) -> EvaluatedAction:
        required_scene = None
        for scene in await context.hue_client_v1.get_scenes():
            if self.match_scene(scene):
                required_scene = scene.model_copy()  # ensure we don't loose model in closure below
                break
        else:
            raise ValueError("Required scene not found")

        async def _is_group_enabled(group_id):
            group = await context.hue_client_v1.get_group(group_id)
            print(group)
            return group.state.any_on

        async def set_scene():
            context.current_scene = required_scene
            if not (await _is_group_enabled(group_id=scene.group)):
                logger.info("Scene not set, because group is not enabled", scene=str(scene))
                return
            res = await context.hue_client_v1.activate_scene(required_scene.group, required_scene.id)
            logger.info("Scene set", res=res, scene=str(scene))

        return set_scene

    def match_scene(self, scene: Scene) -> bool:
        ...


@dataclass
class PlanActionActivateSceneByName(PlanActionActivateScene):
    name: str = ""

    def match_scene(self, scene: Scene) -> bool:
        return scene.name == self.name


@dataclass
class PlanActionActivateSceneById(PlanActionActivateScene):
    id: str = ""

    def match_scene(self, scene: Scene) -> bool:
        return scene.id == self.id


# - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -


@dataclass
class PlanActionToggleCurrentScene(PlanAction):
    transition_time: int | None = None

    async def define_action(self, context: Context) -> EvaluatedAction:
        async def toggle_current_scene():
            if not context.current_scene:
                logger.error("Can't toggle scene, because it was not set yet")
                return
            await context.hue_client_v1.toggle_light(context.current_scene.group)

        return toggle_current_scene
