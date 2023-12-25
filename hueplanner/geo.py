import astral
from astral.location import Location
from geopy.geocoders import Nominatim
from timezonefinder import TimezoneFinder

from hueplanner.cache import LRUCacheDecorator

_geolocator = Nominatim(user_agent="hueplanner")

def get_timezone_from_coords(lat, lng):
    """Get the timezone string from latitude and longitude."""
    tf = TimezoneFinder()
    timezone_str = tf.timezone_at(lat=lat, lng=lng)  # returns the timezone as string
    return timezone_str


@LRUCacheDecorator(cache_size=10, cache_file="./.geocache/cache.db")
def get_location(city_name: str, region: str | None = None) -> Location:
    """Resolve latitude, longitude, and timezone from city name and country"""
    # Construct the query with additional details if available
    query = f"{city_name}, {region}" if region else city_name
    location = _geolocator.geocode(query)
    # Detect timezone is not available
    tz = (
        location.timezone
        if hasattr(location, "timezone")
        else get_timezone_from_coords(location.latitude, location.longitude)
    )
    if not location:
        raise Exception("City not found. Please check the city name.")

    return Location(
        astral.LocationInfo(
            name=location.address,
            region=region,
            timezone=tz,
            latitude=location.latitude,
            longitude=location.longitude,
        )
    )
