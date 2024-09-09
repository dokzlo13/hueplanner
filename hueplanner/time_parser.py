from __future__ import annotations

import re
from datetime import datetime, timedelta, tzinfo

import pytimeparse

from hueplanner.storage.interface import IKeyValueCollection


class TimeParser:
    def __init__(self, tz: tzinfo, variables_collections: list[IKeyValueCollection]):
        self.tz = tz
        self.variables_collections = variables_collections

    async def parse(self, input_time: str):
        # Match @variable pattern
        variable_match = re.match(r"@(\w+)", input_time)
        base_time = None

        if variable_match:
            var_name = variable_match.group(1)
            if var_name == "now":  # Special case for @now
                base_time = datetime.now(tz=self.tz)
            else:
                for collection in self.variables_collections:
                    base_time = await collection.get(var_name)
                    if base_time is not None:
                        break
            if base_time is None:
                raise ValueError(f"Time variable '@{var_name}' is not defined.")
        else:
            # Match XX:XX pattern for exact time (e.g., 13:00)
            time_match = re.match(r"(\d{1,2}):(\d{2})", input_time)
            if time_match:
                hours, minutes = map(int, time_match.groups())
                base_time = datetime.now(self.tz).replace(hour=hours, minute=minutes, second=0, microsecond=0)

        if base_time is None:
            raise ValueError(f"Input time '{input_time}' is not recognized as a valid time format.")

        # Now, extract and parse the modifier (if any)
        modifier_match = re.search(r"([-+])\s*(.*)", input_time)
        if modifier_match:
            sign, duration_str = modifier_match.groups()
            duration = pytimeparse.parse(duration_str.strip())
            if duration is None:
                raise ValueError(f"Could not parse duration '{duration_str}'")

            # Apply the parsed timedelta to the base time
            if sign == "-":
                duration = -duration
            return base_time + timedelta(seconds=duration)

        return base_time


# Mocked IKeyValueCollection for testing
class MockKeyValueCollection:
    def __init__(self, data):
        self.data = data

    async def get(self, key):
        return self.data.get(key)


# Unit test for TimeParser with pytimeparse integration
def test_time_parser():
    variables = {
        "dawn": datetime(2023, 1, 1, 6, 0),
        "noon": datetime(2023, 1, 1, 12, 0),
        "midnight": datetime(2023, 1, 1, 0, 0),
    }

    # Mock time zone for testing
    class MockTimezone(tzinfo):
        def utcoffset(self, dt):
            return timedelta(hours=0)

        def dst(self, dt):
            return timedelta(0)

    tz = MockTimezone()
    parser = TimeParser(tz, [MockKeyValueCollection(variables)])

    # Test @variable parsing
    assert parser.parse("@dawn") == datetime(2023, 1, 1, 6, 0), "Variable parsing failed"

    # Test exact time parsing
    assert parser.parse("13:00") == datetime.now(tz).replace(
        hour=13, minute=0, second=0, microsecond=0
    ), "Exact time parsing failed"

    # Test positive modifier with pytimeparse
    assert parser.parse("@dawn + 1h30m") == datetime(2023, 1, 1, 7, 30), "Positive modifier parsing failed"

    # Test negative modifier with pytimeparse
    assert parser.parse("@noon - 40m") == datetime(2023, 1, 1, 11, 20), "Negative modifier parsing failed"

    print("All tests passed!")


if __name__ == "__main__":
    test_time_parser()
