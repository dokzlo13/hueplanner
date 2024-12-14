from typing import Literal

from pydantic import BaseModel

from .general import Error, Metadata, ResourceIdentifier


class Zone(BaseModel):
    """Zone model for retrieving zone information."""

    type: Literal["zone"] = "zone"
    id: str
    id_v1: str | None
    children: list[ResourceIdentifier]
    services: list[ResourceIdentifier]
    metadata: Metadata


class ZoneGetResponse(BaseModel):
    """Response model for Zone API."""

    errors: list[Error]
    data: list[Zone]
