import inspect
from typing import Awaitable, Callable

from .interface import EvaluatedAction, PlanAction


class PlanActionCallback(PlanAction):
    def __init__(self, callback: Callable[..., None] | Callable[..., Awaitable[None]], *args, **kwargs) -> None:
        super().__init__()
        self._callback = callback
        self._args = args
        self._kwargs = kwargs

    async def define_action(self) -> EvaluatedAction:
        async def action():
            if inspect.iscoroutinefunction(self._callback):
                await self._callback(*self._args, **self._kwargs)  # Await if it's awaitable
            else:
                self._callback(*self._args, **self._kwargs)  # Call directly if it's not awaitable

        return action
