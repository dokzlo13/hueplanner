from typing import Literal

from annotated_types import Ge, Gt, Le, Len
from pydantic import BaseModel, Field
from typing_extensions import Annotated


Rtype = Literal[
    "device",
    "bridge_home",
    "room",
    "zone",
    "service_group",
    "light",
    "button",
    "relative_rotary",
    "temperature",
    "light_level",
    "motion",
    "camera_motion",
    "entertainment",
    "contact",
    "tamper",
    "grouped_light",
    "grouped_motion",
    "grouped_light_level",
    "device_power",
    "device_software_update",
    "zigbee_bridge_connectivity",
    "zigbee_connectivity",
    "zgp_connectivity",
    "remote_access",
    "bridge",
    "zigbee_device_discovery",
    "system_update",
    "homekit",
    "matter",
    "matter_fabric",
    "scene",
    "entertainment_configuration",
    "public_image",
    "auth_v1",
    "behavior_script",
    "behavior_instance",
    "geofence",
    "geofence_client",
    "geolocation",
    "smart_scene",
]
Archetype = Literal[
    "unknown_archetype",
    "classic_bulb",
    "sultan_bulb",
    "flood_bulb",
    "spot_bulb",
    "candle_bulb",
    "luster_bulb",
    "pendant_round",
    "pendant_long",
    "ceiling_round",
    "ceiling_square",
    "floor_shade",
    "floor_lantern",
    "table_shade",
    "recessed_ceiling",
    "recessed_floor",
    "single_spot",
    "double_spot",
    "table_wash",
    "wall_lantern",
    "wall_shade",
    "flexible_lamp",
    "ground_spot",
    "wall_spot",
    "plug",
    "hue_go",
    "hue_lightstrip",
    "hue_iris",
    "hue_bloom",
    "bollard",
    "wall_washer",
    "hue_play",
    "vintage_bulb",
    "vintage_candle_bulb",
    "ellipse_bulb",
    "triangle_bulb",
    "small_globe_bulb",
    "large_globe_bulb",
    "edison_bulb",
    "christmas_tree",
    "string_light",
    "hue_centris",
    "hue_lightstrip_tv",
    "hue_lightstrip_pc",
    "hue_tube",
    "hue_signe",
    "pendant_spot",
    "ceiling_horizontal",
    "ceiling_tube",
    "up_and_down",
    "up_and_down_up",
    "up_and_down_down",
    "hue_floodlight_camera",
]

# Positive float, constrained between 0 and 100
PositiveFloat = Annotated[float, Gt(0), Le(100)]

# Brightness percentage with a minimum value (for dimming)
Brightness = Annotated[float, Gt(0), Le(100)]

# Percentages for mirek values and min/max levels
Mirek = Annotated[int, Ge(153), Le(500)]


# Type for CIE XY Color gamut positions
# XYColor = Annotated[dict, Len(2)]  # Expecting two keys (x, y)
class XYColor(BaseModel):
    x: float
    y: float


class GamutColor(BaseModel):
    red: XYColor
    green: XYColor
    blue: XYColor


# Define Color model, with optional gamut information
class Color(BaseModel):
    xy: XYColor
    gamut: GamutColor | None = None
    gamut_type: Literal["A", "B", "C", "other"] | None = None


# Define Mirek schema model for color temperature
class MirekSchema(BaseModel):
    mirek_minimum: Mirek
    mirek_maximum: Mirek


# Define ColorTemperature model
class ColorTemperature(BaseModel):
    mirek: Mirek
    mirek_valid: bool
    mirek_schema: MirekSchema


# Define Dimming model
class Dimming(BaseModel):
    brightness: Brightness
    min_dim_level: PositiveFloat


# Define Owner model (removed regex as per request)
class Owner(BaseModel):
    rid: str  # Removed regex validation
    rtype: Rtype


# This one is called differently for update response
ResourceIdentifier = Owner


# Define Metadata model
class Metadata(BaseModel):
    name: Annotated[str, Len(1, 32)]  # String with length constraints (1 to 32)
    archetype: Archetype
    function: Literal["functional", "decorative", "mixed", "unknown"]


# Define Powerup feature model
class PowerUp(BaseModel):
    preset: Literal["safety", "powerfail", "last_on_state", "custom"]
    configured: bool


# update stuff


# class MetadataUpdate(BaseModel):
#     name: Annotated[str, Len(1, 32)]
#     archetype: Archetype
#     function: Literal["functional", "decorative", "mixed", "unknown"]


# Identify action
class IdentifyAction(BaseModel):
    action: Literal["identify"] = "identify"


# On/Off model
class OnOff(BaseModel):
    on: bool


# Dimming control model for updates
class DimmingUpdate(BaseModel):
    brightness: Brightness


# Dimming delta model for updates
class DimmingDeltaUpdate(BaseModel):
    action: Literal["up", "down", "stop"]
    brightness_delta: Brightness


# Color Temperature model for updates
class ColorTemperatureUpdate(BaseModel):
    mirek: Mirek


# Color Temperature Delta model for updates
class ColorTemperatureDeltaUpdate(BaseModel):
    action: Literal["up", "down", "stop"]
    mirek_delta: Annotated[int, Le(347)]


# Color update model
class ColorUpdate(BaseModel):
    xy: XYColor


# Dynamics control model for updates
class DynamicsUpdate(BaseModel):
    duration: int
    speed: Annotated[float, Gt(0), Le(1)]  # Speed of dynamic palette


# Alert action for updates
class AlertUpdate(BaseModel):
    action: Literal["breathe"]


# Signaling model for updates
class SignalingUpdate(BaseModel):
    signal: Literal["no_signal", "on_off", "on_off_color", "alternating"]
    duration: Annotated[int, Ge(1), Le(65534000)]  # In milliseconds
    colors: list[XYColor]  # Min 1 and Max 2 colors


# Gradient update model
class GradientPointUpdate(BaseModel):
    color: ColorUpdate


class GradientUpdate(BaseModel):
    points: Annotated[list[GradientPointUpdate], Len(2, 5)]  # Minimum of 2 points, max 5
    mode: Literal["interpolated_palette", "interpolated_palette_mirrored", "random_pixelated"]


# Effects model for updates
class EffectsUpdate(BaseModel):
    effect: Literal["prism", "opal", "glisten", "sparkle", "fire", "candle", "no_effect"]


# Timed Effects model for updates
class TimedEffectsUpdate(BaseModel):
    effect: Literal["sunrise", "sunset", "no_effect"]
    duration: Annotated[int, Ge(1), Le(21600000)]  # Duration up to 21600000 ms


# Powerup model for updates
class PowerupOnUpdate(BaseModel):
    mode: Literal["on", "toggle", "previous"]
    on: OnOff | None = None


class PowerupDimmingUpdate(BaseModel):
    mode: Literal["dimming", "previous"]
    dimming: DimmingUpdate | None = None


class PowerupColorUpdate(BaseModel):
    mode: Literal["color_temperature", "color", "previous"]
    color_temperature: ColorTemperatureUpdate | None = None
    color: ColorUpdate | None = None


class PowerupUpdate(BaseModel):
    preset: Literal["safety", "powerfail", "last_on_state", "custom"]
    on: PowerupOnUpdate | None = None
    dimming: PowerupDimmingUpdate | None = None
    color: PowerupColorUpdate | None = None


# final


# Define Error model
class Error(BaseModel):
    description: Annotated[str, Len(1)]  # Description must not be empty


# Define LightGet model
class Light(BaseModel):
    id: str  # Removed regex validation
    id_v1: str | None  # Removed regex validation
    type: Literal["light"]
    metadata: Metadata
    owner: Owner
    dimming: Dimming | None = None
    color_temperature: ColorTemperature | None = None
    color: Color | None = None
    powerup: PowerUp | None = None
    mode: Literal["normal", "streaming"]
    service_id: Annotated[int, Ge(0)]  # Positive integer >= 0


# Define the response body model
class LightGetResponse(BaseModel):
    errors: list[Error]
    data: list[Light]


# Full update request model
class LightUpdateRequest(BaseModel):
    type: Literal["light"] = "light"
    metadata: Metadata | None = None
    identify: IdentifyAction | None = None
    on: OnOff | None = None
    dimming: DimmingUpdate | None = None
    dimming_delta: DimmingDeltaUpdate | None = None
    color_temperature: ColorTemperatureUpdate | None = None
    color_temperature_delta: ColorTemperatureDeltaUpdate | None = None
    color: ColorUpdate | None = None
    dynamics: DynamicsUpdate | None = None
    alert: AlertUpdate | None = None
    signaling: SignalingUpdate | None = None
    gradient: GradientUpdate | None = None
    effects: EffectsUpdate | None = None
    timed_effects: TimedEffectsUpdate | None = None
    powerup: PowerupUpdate | None = None


class LightUpdateResponse(BaseModel):
    errors: list[Error]  # Reusing the Error model
    data: list[ResourceIdentifier]  # List of ResourceIdentifier objects
