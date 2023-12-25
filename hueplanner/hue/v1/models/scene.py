from typing import Dict, List, Optional

from pydantic import BaseModel, Field


class AppData(BaseModel):
    version: int
    data: str


class Scene(BaseModel):
    id: str = None  # type: ignore
    name: str
    type: str
    group: int
    lights: List[str]
    owner: Optional[str] = ""
    recycle: bool
    locked: bool
    appdata: AppData
    picture: Optional[str] = ""
    image: str
    lastupdated: str
    version: int
