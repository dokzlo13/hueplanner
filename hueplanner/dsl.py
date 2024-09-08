from typing import Any, Type

import yaml
from hueplanner.planner.serializable import Serializable

from .planner import (
    ACTION_CLASSES,
    TRIGGER_CLASSES,
    PlanAction,
    PlanActionSequence,
    PlanEntry,
    PlanTrigger,
)


def load_plan(path: str, encoding: str | None = None) -> list[PlanEntry]:
    with open(path, "r", encoding=encoding) as f:
        master_config = yaml.safe_load(f)
        plan_entries = master_config.get("plan", [])
        plan = [load_plan_entry(entry) for entry in plan_entries]
        return plan


def generate_mappings(classes, prefix):
    return {cls.__name__.replace(prefix, ""): cls for cls in classes}


action_map = generate_mappings(ACTION_CLASSES, "PlanAction")
trigger_map = generate_mappings(TRIGGER_CLASSES, "PlanTrigger")


def _load_action(action_data: dict[str, Any]) -> PlanAction:
    type, args = action_data["type"], action_data.get("args", {})
    action_class: Type[Serializable] = action_map[type]
    if action_class is PlanActionSequence:
        action = _load_sequence(args)
    else:
        action = action_class.loads(args)
    return action  # type: ignore


def _load_trigger(trigger_data: dict[str, Any]) -> PlanTrigger:
    type, args = trigger_data["type"], trigger_data.get("args", {})
    trigger_class: Type[Serializable] = trigger_map[type]
    return trigger_class.loads(args)  # type: ignore


def _load_sequence(entries: list[dict[str, Any]]) -> PlanActionSequence:
    items: list[PlanAction] = []
    for entry in entries:
        items.append(_load_action(entry))
    return PlanActionSequence(*items)


def load_plan_entry(entry: dict[str, Any]) -> PlanEntry:
    action = _load_action(entry["action"])
    trigger = _load_trigger(entry["trigger"])
    return PlanEntry(trigger=trigger, action=action)
