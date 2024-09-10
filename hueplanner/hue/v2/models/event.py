from dataclasses import dataclass
from typing import Any

HueEventData = dict[str, Any]


@dataclass
class HueEvent:
    id: str
    data: list[HueEventData]
