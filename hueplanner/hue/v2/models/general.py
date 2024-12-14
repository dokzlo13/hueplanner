from __future__ import annotations

from typing import Literal

from annotated_types import Ge, Gt, Le, Len
from pydantic import BaseModel
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
    #
    # Extra
    "living_room",
    "kitchen",
    "dining",
    "bedroom",
    "kids_bedroom",
    "bathroom",
    "nursery",
    "recreation",
    "office",
    "gym",
    "hallway",
    "toilet",
    "front_door",
    "garage",
    "terrace",
    "garden",
    "driveway",
    "carport",
    "home",
    "downstairs",
    "upstairs",
    "top_floor",
    "attic",
    "guest_room",
    "staircase",
    "lounge",
    "man_cave",
    "computer",
    "studio",
    "music",
    "tv",
    "reading",
    "closet",
    "storage",
    "laundry_room",
    "balcony",
    "porch",
    "barbecue",
    "pool",
    "other",
]

# Brightness = Annotated[float, Gt(0), Le(100)]
Brightness = float
Mirek = Annotated[int, Ge(153), Le(500)]
PositiveFloat = Annotated[float, Gt(0), Le(100)]


class XYColor(BaseModel):
    x: float
    y: float


class GamutColor(BaseModel):
    red: XYColor
    green: XYColor
    blue: XYColor


class Color(BaseModel):
    xy: XYColor
    gamut: GamutColor | None = None
    gamut_type: Literal["A", "B", "C", "other"] | None = None


class MirekSchema(BaseModel):
    mirek_minimum: Mirek
    mirek_maximum: Mirek


class ColorTemperature(BaseModel):
    mirek: Mirek
    mirek_valid: bool | None = None
    mirek_schema: MirekSchema | None = None


class Dimming(BaseModel):
    brightness: Brightness


class OnOff(BaseModel):
    on: bool


class ResourceIdentifier(BaseModel):
    rid: str
    rtype: Rtype


class Metadata(BaseModel):
    name: Annotated[str, Len(1, 32)]
    archetype: Archetype
    function: Literal["functional", "decorative", "mixed", "unknown"] | None = None


class Error(BaseModel):
    description: Annotated[str, Len(1)]


# Unified Effects model
class Effects(BaseModel):
    effect: Literal["prism", "opal", "glisten", "sparkle", "fire", "candle", "no_effect"]


# Unified color setting for actions/updates
class ColorData(BaseModel):
    xy: XYColor


# Unified gradient point
class GradientPointData(BaseModel):
    color: ColorData


# Unified gradient
class GradientData(BaseModel):
    points: Annotated[list[GradientPointData], Len(2, 5)]
    mode: Literal["interpolated_palette", "interpolated_palette_mirrored", "random_pixelated"]


# Unified dynamics (some contexts have only duration, some have duration and speed)
class DynamicsData(BaseModel):
    duration: int
    speed: Annotated[float, Gt(0), Le(1)] | None = None
