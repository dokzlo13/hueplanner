import structlog

from hueplanner.ioc import IOC

from .interface import EvaluatedAction, PlanAction

logger = structlog.getLogger(__name__)


class PlanActionSequence(PlanAction):
    def __init__(self, *actions: tuple[PlanAction, ...]) -> None:
        super().__init__()
        self._actions: tuple[PlanAction, ...] = tuple(item for a in actions for item in self._unpack_nested_sequence(a))

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(items=[" + ", ".join(repr(i) for i in self._actions) + "])"

    def _unpack_nested_sequence(self, action: PlanAction) -> tuple[PlanAction, ...]:
        if isinstance(action, PlanActionSequence):
            return action._actions
        return (action,)

    async def define_action(self, ioc: IOC) -> EvaluatedAction:
        logger.info("Preparing sequence actions", actions=self._actions)

        evaluated_actions: list[EvaluatedAction] = []
        for action in self._actions:
            evaluated_action = await ioc.make(action.define_action)
            evaluated_actions.append(evaluated_action)

        async def run_sequence_evaluated_action():
            logger.info("Sequence action requested", action=repr(self))
            for evaluated_action in evaluated_actions:
                await evaluated_action()

        logger.info("Sequence actions prepared", evaluated_actions=evaluated_actions)
        return run_sequence_evaluated_action
