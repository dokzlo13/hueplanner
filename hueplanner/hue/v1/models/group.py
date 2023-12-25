from typing import Dict, List, Optional

from pydantic import BaseModel, Field


class State(BaseModel):
    all_on: bool
    any_on: bool


class Action(BaseModel):
    on: bool
    bri: Optional[int] = None
    hue: Optional[int] = None
    sat: Optional[int] = None
    effect: Optional[str] = None
    xy: Optional[List[float]] = None
    ct: Optional[int] = None
    alert: Optional[str] = None
    colormode: Optional[str] = None


class Stream(BaseModel):
    proxymode: str
    proxynode: str
    active: bool
    owner: Optional[str] = None


class Location(BaseModel):
    # Define as needed, example with 3D coordinates
    x: float
    y: float
    z: float


class Group(BaseModel):
    id: int = None  # type: ignore
    name: str
    lights: List[str]
    sensors: List[str]
    type: str
    state: State
    recycle: bool
    class_: str = Field(alias="class")
    action: Action
    stream: Optional[Stream] = None
    locations: Optional[Dict[str, List[float]]] = None
