import structlog

from hueplanner.ioc import IOC

from .interface import EvaluatedCondition, PlanCondition

logger = structlog.getLogger(__name__)


class PlanConditionContainer(PlanCondition):
    def __init__(self, *conditions: tuple[PlanCondition, ...]) -> None:
        super().__init__()
        self._conditions: tuple[PlanCondition, ...] = tuple(
            item for a in conditions for item in self._unpack_nested_sequence(a)
        )

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(items=[" + ", ".join(repr(i) for i in self._conditions) + "])"

    def _unpack_nested_sequence(self, action: PlanCondition) -> tuple[PlanCondition, ...]:
        if isinstance(action, PlanConditionContainer):
            return action._conditions
        return (action,)

    async def define_condition(self, ioc: IOC) -> EvaluatedCondition:
        logger.info("Preparing sequence condition", actions=self._conditions)

        evaluated_conditions: list[EvaluatedCondition] = []
        for cond in self._conditions:
            evaluated_cond = await ioc.make(cond.define_condition)
            evaluated_conditions.append(evaluated_cond)

        logger.info("Sequence condition prepared", evaluated_conditions=evaluated_conditions)
        return self._make_condition(evaluated_conditions)

    def _make_condition(self, evaluated_condition: list[EvaluatedCondition]) -> EvaluatedCondition: ...


class PlanConditionOr(PlanConditionContainer):
    def _make_condition(self, evaluated_conditions: list[EvaluatedCondition]) -> EvaluatedCondition:
        async def run_sequence_evaluated_condition() -> bool:
            logger.info("OR condition requested", action=repr(self))
            for evaluated_cond in evaluated_conditions:
                res = await evaluated_cond()
                if res:
                    return res
            return False

        return run_sequence_evaluated_condition


class PlanConditionAnd(PlanConditionContainer):
    def _make_condition(self, evaluated_conditions: list[EvaluatedCondition]) -> EvaluatedCondition:
        async def run_sequence_evaluated_condition() -> bool:
            logger.info("OR condition requested", action=repr(self))
            for evaluated_cond in evaluated_conditions:
                res = await evaluated_cond()
                if not res:
                    return False
            return True

        return run_sequence_evaluated_condition
