from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, time, timedelta
from typing import Any, Callable

import astral
import structlog
import zoneinfo
from astral.location import Location
from astral.sun import Observer, dawn, dusk, midnight, noon, sunrise, sunset
from geopy.geocoders import Nominatim
from pydantic import BaseModel
from timezonefinder import TimezoneFinder

from hueplanner.planner.serializable import Serializable
from hueplanner.storage.interface import IKeyValueStorage

from .interface import EvaluatedAction, PlanAction

logger = structlog.getLogger(__name__)

_geolocator = Nominatim(user_agent="hueplanner")


@dataclass
class AstronomicalEvent:
    event_func: Callable[[Any, Any, Any], datetime]
    default_time: time


# Default average times for astronomical events (adjust these as needed)
DEFAULT_TIMES = {
    "dawn": datetime.strptime("06:00", "%H:%M").time(),
    "sunrise": datetime.strptime("06:30", "%H:%M").time(),
    "noon": datetime.strptime("12:00", "%H:%M").time(),
    "sunset": datetime.strptime("18:30", "%H:%M").time(),
    "dusk": datetime.strptime("19:00", "%H:%M").time(),
    "midnight": datetime.strptime("00:00", "%H:%M").time(),
}

ASTRONOMICAL_EVENTS = {
    "dawn": AstronomicalEvent(dawn, DEFAULT_TIMES["dawn"]),
    "sunrise": AstronomicalEvent(sunrise, DEFAULT_TIMES["sunrise"]),
    "noon": AstronomicalEvent(noon, DEFAULT_TIMES["noon"]),
    "sunset": AstronomicalEvent(sunset, DEFAULT_TIMES["sunset"]),
    "dusk": AstronomicalEvent(dusk, DEFAULT_TIMES["dusk"]),
    "midnight": AstronomicalEvent(midnight, DEFAULT_TIMES["midnight"]),
}


def get_timezone_from_coords(lat, lng):
    """Get the timezone string from latitude and longitude."""
    tf = TimezoneFinder()
    timezone_str = tf.timezone_at(lat=lat, lng=lng)  # returns the timezone as string
    return timezone_str


def location_from_name(location_name: str) -> Location:
    """Resolve latitude, longitude, and timezone from city name and country"""
    # Construct the query with additional details if available
    location = _geolocator.geocode(location_name)
    logger.debug("Location geocoded:", loc=location)
    # Detect timezone is not available
    if not location:
        raise Exception("City not found. Please check the city name.")
    tz = (
        location.timezone
        if hasattr(location, "timezone")
        else get_timezone_from_coords(location.latitude, location.longitude)
    )
    logger.debug("Timezone evaluated:", tz=tz)

    return Location(
        astral.LocationInfo(
            name=location.address,
            region="",
            timezone=tz,
            latitude=location.latitude,
            longitude=location.longitude,
        )
    )


def location_from_coords(lat, lng) -> Location:
    return Location(
        astral.LocationInfo(
            name="",
            region="",
            timezone=get_timezone_from_coords(lat, lng),
            latitude=lat,
            longitude=lng,
        )
    )


def calculate_astronomical_event(event: AstronomicalEvent, observer, date, tzinfo) -> datetime:
    try:
        return event.event_func(observer, date=date, tzinfo=tzinfo)
    except ValueError:
        logger.warning(
            f"Failed to calculate {event.event_func.__name__} for {date}, trying to fallback (calculate next day)"
        )
        try:
            return event.event_func(observer, date=date + timedelta(days=1), tzinfo=tzinfo)
        except ValueError:
            logger.error(
                f"Failed to calculate {event.event_func.__name__} for next day as well, using fallback",
                fallback_time=event.default_time,
            )
            return datetime.combine(date, event.default_time)


def astronomical_variables_from_location(location: Location, now: datetime | None = None) -> dict[str, datetime]:
    variables: dict[str, datetime] = {}
    if now is None:
        now = datetime.now(tz=zoneinfo.ZoneInfo(location.timezone))
    observer = Observer(latitude=location.latitude, longitude=location.longitude, elevation=0)

    # Calculate each astronomical event with error handling
    for event_name, event in ASTRONOMICAL_EVENTS.items():
        if event_name == "midnight":
            try:
                variables[event_name] = event.event_func(observer, date=now, tzinfo=location.timezone) + timedelta(
                    days=1
                )
            except ValueError:
                logger.warning(f"Failed to calculate {event_name} for {now}")
                variables[event_name] = datetime.combine(now.date(), event.default_time) + timedelta(days=1)
        else:
            variables[event_name] = calculate_astronomical_event(event, observer, now, location.timezone)

    return variables


@dataclass(kw_only=True)
class PlanActionPopulateGeoVariables(PlanAction, Serializable):
    variables_db: str
    cache_db: str | None
    location_name: str | None
    lat: float | None
    lng: float | None
    # auto_set_timezone: bool

    class _Model(BaseModel):
        variables_db: str = "geo_variables"
        cache_db: str | None = None
        location_name: str | None = None
        lat: float | None = None
        lng: float | None = None
        # auto_set_timezone: bool = False

    async def define_action(self, storage: IKeyValueStorage) -> EvaluatedAction:
        location = None

        if self.cache_db:
            cache = await storage.create_collection(self.cache_db)
            location = await cache.get("location")
            if location:
                logger.info("Location available from cache", location=location)

        if not location:
            if self.lat is not None and self.lng is not None:
                location = location_from_coords(self.lat, self.lng)
                logger.info("Using location fron lat/lng", location=location)

            elif self.location_name is not None:
                logger.warning("Obtaining location from geocoder...")
                location = location_from_name(self.location_name)
                logger.info("Geocoded location obtained form geocoder", location=location)

            else:
                raise ValueError("PopulateGeoVariables action requires lat/lng or location_name provided")

        if not location:

            async def nop():
                logger.warning("Location unavailable, no time variables calculated")

            return nop

        if self.cache_db:
            await cache.set("location", location)
            logger.info("Location cache updated", location=location)

        async def action():
            variables = await storage.create_collection(self.variables_db)
            if (await variables.size()) > 0:
                await variables.delete_all()
                logger.warning("time_variables cache flushed")

            for k, v in astronomical_variables_from_location(location).items():
                logger.info(f"Astronomical event for today: {k:<10}: {str(v)}")
                await variables.set(k, v)

        return action
