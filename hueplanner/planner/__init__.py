from .actions import (
    PlanAction,
    PlanActionCallback,
    PlanActionFlushDb,
    PlanActionPopulateGeoVariables,
    PlanActionPrintSchedule,
    PlanActionReEvaluatePlan,
    PlanActionRunClosestSchedule,
    PlanActionRunIf,
    PlanActionSequence,
    PlanActionStoreSceneById,
    PlanActionStoreSceneByName,
    PlanActionToggleStoredScene,
    PlanActionUpdateLightV2,
)
from .conditions import (
    EvaluatedCondition,
    PlanCondition,
    PlanConditionAnd,
    PlanConditionContainer,
    PlanConditionDBKeyNotSet,
    PlanConditionOr,
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
    PlanActionRunIf,
    ## This cannot be parsed from config yet
    # PlanActionCallback,
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

CONDITION_CLASSES = [
    PlanConditionAnd,
    PlanConditionOr,
    PlanConditionDBKeyNotSet,
]
