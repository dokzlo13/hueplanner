from typing import Dict, List, Optional, Tuple

from pydantic import BaseModel


class LightState(BaseModel):
    on: bool
    bri: Optional[int] = None
    hue: Optional[int] = None
    sat: Optional[int] = None
    effect: Optional[str] = None
    xy: Optional[List[float]] = None
    ct: Optional[int] = None
    alert: Optional[str] = None
    colormode: Optional[str] = None
    mode: str
    reachable: bool


class SwUpdate(BaseModel):
    state: str
    lastinstall: str


class Control(BaseModel):
    mindimlevel: Optional[int] = None
    maxlumen: Optional[int] = None
    colorgamuttype: Optional[str] = None
    colorgamut: Optional[List[Tuple[float, float]]] = None
    ct: Optional[Dict[str, int]] = None


class Streaming(BaseModel):
    renderer: bool
    proxy: bool


class Capabilities(BaseModel):
    certified: bool
    control: Control
    streaming: Streaming


class Startup(BaseModel):
    mode: str
    configured: bool


class Config(BaseModel):
    archetype: str
    function: str
    direction: str
    startup: Startup


class Light(BaseModel):
    id: int = None  # type: ignore
    state: LightState
    swupdate: SwUpdate
    type: str
    name: str
    modelid: str
    manufacturername: str
    productname: str
    capabilities: Capabilities
    config: Config
    uniqueid: str
    swversion: str
    swconfigid: str
    productid: str
