from .actions import (
    PlanAction,
    PlanActionCallback,
    PlanActionFlushDb,
    PlanActionPopulateGeoVariables,
    PlanActionPrintSchedule,
    PlanActionReEvaluatePlan,
    PlanActionSequence,
    PlanActionStoreSceneById,
    PlanActionStoreSceneByName,
    PlanActionToggleStoredScene,
    PlanActionWithEvaluationCondition,
    PlanActionWithRuntimeCondition,
)
from .planner import PlanEntry, Planner, Plan
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
    PlanActionPopulateGeoVariables,
    PlanActionPrintSchedule,
    PlanActionFlushDb,
    PlanActionReEvaluatePlan,
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
