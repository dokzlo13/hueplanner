from dataclasses import dataclass
from typing import Any

# TODO: Make full schema for this one
HueEventData = dict[str, Any]


@dataclass
class HueEvent:
    id: str
    data: list[HueEventData]
