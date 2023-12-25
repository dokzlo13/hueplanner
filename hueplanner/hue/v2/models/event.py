from dataclasses import dataclass
from typing import Any


@dataclass
class HueEvent:
    id: str
    data: list[dict[str, Any]]
