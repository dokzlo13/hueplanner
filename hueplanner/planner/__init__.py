from .actions import (
    PlanAction,
    PlanActionStoreSceneById,
    PlanActionStoreSceneByName,
    PlanActionCallback,
    PlanActionSequence,
    PlanActionToggleStoredScene,
    PlanActionWithEvaluationCondition,
    PlanActionWithRuntimeCondition,
)
from .context import Context
from .planner import PlanEntry, Planner
from .triggers import (
    PlanTrigger,
    PlanTriggerImmediately,
    PlanTriggerOnce,
    PlanTriggerOnHueButtonEvent,
    PlanTriggerPeriodic,
)

ACTION_CLASSES = [
    PlanActionStoreSceneById,
    PlanActionStoreSceneByName,
    PlanActionSequence,
    PlanActionToggleStoredScene,
    ## This cannot be parsed from config yet
    # PlanActionCallback,
    # PlanActionWithEvaluationCondition,
    # PlanActionWithRuntimeCondition,
]

TRIGGER_CLASSES = [
    PlanTriggerImmediately,
    PlanTriggerOnce,
    PlanTriggerOnHueButtonEvent,
    PlanTriggerPeriodic,
]
