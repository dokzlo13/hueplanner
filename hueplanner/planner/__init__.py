from .actions import (
    PlanAction,
    PlanActionCallback,
    PlanActionFlushDb,
    PlanActionPopulateGeoVariables,
    PlanActionPrintSchedule,
    PlanActionReEvaluatePlan,
    PlanActionRunClosestSchedule,
    PlanActionSequence,
    PlanActionStoreSceneById,
    PlanActionStoreSceneByName,
    PlanActionToggleStoredScene,
    PlanActionUpdateLightV2,
    PlanActionWithEvaluationCondition,
    PlanActionWithRuntimeCondition,
)
from .planner import Plan, PlanEntry, Planner
from .triggers import (
    PlanTrigger,
    PlanTriggerDaily,
    PlanTriggerHourly,
    PlanTriggerImmediately,
    PlanTriggerMinutely,
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
    PlanActionRunClosestSchedule,
    PlanActionUpdateLightV2,
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
    PlanTriggerDaily,
    PlanTriggerHourly,
    PlanTriggerMinutely,
]
