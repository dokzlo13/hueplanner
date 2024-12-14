from __future__ import annotations

from typing import Literal

from annotated_types import Ge, Gt, Le, Len
from pydantic import BaseModel
from typing_extensions import Annotated

from .general import (
    Brightness,
    Color,
    ColorData,
    ColorTemperature,
    Dimming,
    DynamicsData,
    Effects,
    Error,
    GradientData,
    Metadata,
    Mirek,
    OnOff,
    ResourceIdentifier,
    Rtype,
    XYColor,
)
from .light import LightUpdateRequest


# Scene actions now use the unified models
class SceneActionData(BaseModel):
    on: OnOff | None = None
    dimming: Dimming | None = None
    color: ColorData | None = None
    color_temperature: ColorTemperature | None = None
    gradient: GradientData | None = None
    effects: Effects | None = None
    dynamics: DynamicsData | None = None

    def as_light_update_request(self) -> LightUpdateRequest:
        return LightUpdateRequest(
            on=self.on,
            dimming=self.dimming,
            color=self.color,
            color_temperature=self.color_temperature,
            gradient=self.gradient,
            effects=self.effects,
            dynamics=self.dynamics,
        )


class Action(BaseModel):
    target: ResourceIdentifier
    action: SceneActionData


class ColorPalette(BaseModel):
    color: Color
    dimming: Dimming


class DimmingFeatureBasic(BaseModel):
    brightness: Brightness


class ColorTemperaturePalette(BaseModel):
    color_temperature: ColorTemperature
    dimming: Dimming


class EffectFeatureBasic(BaseModel):
    effect: Literal["prism", "opal", "glisten", "sparkle", "fire", "candle", "no_effect"]


class Palette(BaseModel):
    color: list[ColorPalette]
    dimming: list[DimmingFeatureBasic]
    color_temperature: list[ColorTemperaturePalette]
    effects: list[EffectFeatureBasic]


class SceneMetadata(BaseModel):
    name: Annotated[str, Len(1, 32)]
    image: ResourceIdentifier | None = None
    appdata: Annotated[str, Len(1, 16)] | None = None


class SceneStatus(BaseModel):
    active: Literal["inactive", "static", "dynamic_palette"] | None = None


class Scene(BaseModel):
    type: Literal["scene"] = "scene"
    id: str
    id_v1: str | None
    actions: list[Action]
    palette: Palette | None = None
    metadata: SceneMetadata
    group: ResourceIdentifier
    speed: Annotated[float, Ge(0), Le(1)]
    auto_dynamic: bool
    status: SceneStatus | None = None


class SceneGetResponse(BaseModel):
    errors: list[Error]
    data: list[Scene]
