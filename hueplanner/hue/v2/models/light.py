from __future__ import annotations

from typing import Literal

from annotated_types import Ge, Gt, Le, Len
from pydantic import BaseModel
from typing_extensions import Annotated

from .general import (
    Archetype,
    Brightness,
    Color,
    ColorData,
    ColorTemperature,
    Dimming,
    DynamicsData,
    Effects,
    Error,
    GamutColor,
    GradientData,
    Metadata,
    Mirek,
    MirekSchema,
    OnOff,
    PositiveFloat,
    ResourceIdentifier,
    Rtype,
    XYColor,
)


class IdentifyAction(BaseModel):
    action: Literal["identify"] = "identify"


class ColorTemperatureDeltaUpdate(BaseModel):
    action: Literal["up", "down", "stop"]
    mirek_delta: Annotated[int, Le(347)]


# For dimming deltas
class DimmingDeltaUpdate(BaseModel):
    action: Literal["up", "down", "stop"]
    brightness_delta: Brightness


class AlertUpdate(BaseModel):
    action: Literal["breathe"]


class SignalingUpdate(BaseModel):
    signal: Literal["no_signal", "on_off", "on_off_color", "alternating"]
    duration: Annotated[int, Ge(1), Le(65534000)]
    colors: list[XYColor]


class TimedEffectsUpdate(BaseModel):
    effect: Literal["sunrise", "sunset", "no_effect"]
    duration: Annotated[int, Ge(1), Le(21600000)]


class PowerupOnUpdate(BaseModel):
    mode: Literal["on", "toggle", "previous"]
    on: OnOff | None = None


class PowerupDimmingUpdate(BaseModel):
    mode: Literal["dimming", "previous"]
    dimming: Dimming | None = None


class PowerupColorUpdate(BaseModel):
    mode: Literal["color_temperature", "color", "previous"]
    color_temperature: ColorTemperature | None = None
    color: ColorData | None = None


class PowerUp(BaseModel):
    preset: Literal["safety", "powerfail", "last_on_state", "custom"]
    configured: bool


class PowerupUpdate(BaseModel):
    preset: Literal["safety", "powerfail", "last_on_state", "custom"]
    on: PowerupOnUpdate | None = None
    dimming: PowerupDimmingUpdate | None = None
    color: PowerupColorUpdate | None = None


class Light(BaseModel):
    id: str
    id_v1: str | None
    type: Literal["light"]
    metadata: Metadata
    owner: ResourceIdentifier
    dimming: Dimming | None = None
    color_temperature: ColorTemperature | None = None
    color: Color | None = None
    powerup: PowerUp | None = None
    mode: Literal["normal", "streaming"]
    service_id: Annotated[int, Ge(0)]


class LightGetResponse(BaseModel):
    errors: list[Error]
    data: list[Light]


class LightUpdateRequest(BaseModel):
    type: Literal["light"] = "light"
    metadata: Metadata | None = None
    identify: IdentifyAction | None = None
    on: OnOff | None = None
    dimming: Dimming | None = None
    dimming_delta: DimmingDeltaUpdate | None = None
    color_temperature: ColorTemperature | None = None
    color_temperature_delta: ColorTemperatureDeltaUpdate | None = None
    color: ColorData | None = None
    dynamics: DynamicsData | None = None
    alert: AlertUpdate | None = None
    signaling: SignalingUpdate | None = None
    gradient: GradientData | None = None
    effects: Effects | None = None
    timed_effects: TimedEffectsUpdate | None = None
    powerup: PowerupUpdate | None = None


class LightUpdateResponse(BaseModel):
    errors: list[Error]
    data: list[ResourceIdentifier]
