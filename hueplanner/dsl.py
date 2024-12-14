from typing import Any, Type

import yaml

from hueplanner.planner.serializable import Serializable

from .planner import (
    ACTION_CLASSES,
    CONDITION_CLASSES,
    TRIGGER_CLASSES,
    PlanAction,
    PlanActionDelayed,
    PlanActionRunIf,
    PlanActionSequence,
    PlanCondition,
    PlanConditionAnd,
    PlanConditionContainer,
    PlanConditionOr,
    PlanEntry,
    PlanTrigger,
)


def load_plan(path: str, encoding: str | None = None) -> list[PlanEntry]:
    with open(path, "r", encoding=encoding) as f:
        master_config = yaml.safe_load(f)
        plan_entries = master_config.get("plan", [])
        return load_plan_from_obj(plan_entries)


def load_plan_from_obj(plan_data: list[dict[str, Any]]) -> list[PlanEntry]:
    return [load_plan_entry(entry) for entry in plan_data]


def generate_mappings(classes, prefix):
    return {cls.__name__.replace(prefix, ""): cls for cls in classes}


action_map = generate_mappings(ACTION_CLASSES, "PlanAction")
trigger_map = generate_mappings(TRIGGER_CLASSES, "PlanTrigger")
condition_map = generate_mappings(CONDITION_CLASSES, "PlanCondition")


def _load_action(action_data: dict[str, Any]) -> PlanAction:
    type, args = action_data["type"], action_data.get("args", {})
    action_class: Type[Serializable] = action_map[type]
    if action_class is PlanActionSequence:
        action = _load_action_sequence(args)
    elif action_class is PlanActionRunIf:
        action = _load_if_action(args)
    elif action_class is PlanActionDelayed:
        action = _load_delayed_action(args)
    else:
        action = action_class.loads(args)
    return action  # type: ignore


def _load_trigger(trigger_data: dict[str, Any]) -> PlanTrigger:
    type, args = trigger_data["type"], trigger_data.get("args", {})
    trigger_class: Type[Serializable] = trigger_map[type]
    return trigger_class.loads(args)  # type: ignore


def _load_action_sequence(entries: list[dict[str, Any]]) -> PlanActionSequence:
    items: list[PlanAction] = []
    for entry in entries:
        items.append(_load_action(entry))
    return PlanActionSequence(*items)  # type: ignore


def _load_condition_sequence(
    sequence_class: Type[PlanConditionContainer], entries: list[dict[str, Any]]
) -> PlanConditionContainer:
    items: list[PlanCondition] = []
    for entry in entries:
        items.append(_load_condition(entry))
    return sequence_class(*items)  # type: ignore


def _load_condition(condition_data: dict[str, Any]) -> PlanCondition:
    type, args = condition_data["type"], condition_data.get("args", {})
    condition_class: Type[Serializable] = condition_map[type]
    if condition_class is PlanConditionAnd or condition_class is PlanConditionOr:
        condition = _load_condition_sequence(condition_class, args)
    else:
        condition = condition_class.loads(args)
    return condition  # type: ignore


def _load_if_action(args: dict[str, Any]) -> PlanActionRunIf:
    action = _load_action(args["action"])
    condition = _load_condition(args["condition"])
    return PlanActionRunIf(condition=condition, action=action)


def _load_delayed_action(args: dict[str, Any]) -> PlanActionDelayed:
    action = _load_action(args["action"])
    return PlanActionDelayed(action=action, delay=args["delay"])


def load_plan_entry(entry: dict[str, Any]) -> PlanEntry:
    action = _load_action(entry["action"])
    trigger = _load_trigger(entry["trigger"])
    return PlanEntry(trigger=trigger, action=action)
