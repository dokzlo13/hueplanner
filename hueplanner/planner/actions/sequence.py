from .interface import PlanAction, EvaluatedAction
from hueplanner.ioc import IOC


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

    async def define_action(self, ioc: IOC) -> EvaluatedAction:
        evaluated_actions: list[EvaluatedAction] = []
        for action in self._actions:
            evaluated_action = await ioc.make(action.define_action)
            evaluated_actions.append(evaluated_action)

        async def sequence_evaluated_action():
            for evaluated_action in evaluated_actions:
                await evaluated_action()

        return sequence_evaluated_action
