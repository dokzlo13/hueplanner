from datetime import datetime, timedelta

import astral
import structlog
import zoneinfo
from astral.location import Location
from geopy.geocoders import Nominatim
from timezonefinder import TimezoneFinder

logger = structlog.getLogger(__name__)

_geolocator = Nominatim(user_agent="hueplanner")


def get_timezone_from_coords(lat, lng):
    """Get the timezone string from latitude and longitude."""
    tf = TimezoneFinder()
    timezone_str = tf.timezone_at(lat=lat, lng=lng)  # returns the timezone as string
    return timezone_str


def get_location(location_name: str) -> Location:
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


def astronomical_variables_from_location(location: Location, now: datetime | None = None) -> dict[str, datetime]:
    variables: dict[str, datetime] = {}
    if now is None:
        now = datetime.now(tz=zoneinfo.ZoneInfo(location.timezone))
    dt: datetime
    for tag, dt in location.sun(date=now).items():
        variables[tag] = dt
    variables["midnight"] = location.midnight(date=now) + timedelta(days=1)
    return variables
