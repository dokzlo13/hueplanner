import astral
import structlog
from astral.location import Location
from geopy.geocoders import Nominatim
from timezonefinder import TimezoneFinder

from hueplanner.cache import LRUCacheDecorator

logger = structlog.getLogger(__name__)

_geolocator = Nominatim(user_agent="hueplanner")


def get_timezone_from_coords(lat, lng):
    """Get the timezone string from latitude and longitude."""
    tf = TimezoneFinder()
    timezone_str = tf.timezone_at(lat=lat, lng=lng)  # returns the timezone as string
    return timezone_str


@LRUCacheDecorator(cache_size=10, cache_file="./.geocache/cache.db")
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
